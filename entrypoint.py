import os
import sys
import logging
import gnupg
import git
import shutil
from key import detectPublicKey, importPrivateKey

debug = os.environ.get('INPUT_DEBUG', False)

if debug:
    logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)
else:
    logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.INFO)

if __name__ == '__main__':
    logging.info('-- Parsing input --')

    github_token = os.environ.get('INPUT_GITHUB_TOKEN')
    arch = os.environ.get('INPUT_ARCH')
    version = os.environ.get('INPUT_VERSION')
    deb_file = os.environ.get('INPUT_FILE')
    deb_file_version = os.environ.get('INPUT_FILE_TARGET_VERSION')
    github_repo = os.environ.get('GITHUB_REPOSITORY')

    gh_branch = os.environ.get('INPUT_PAGE_BRANCH', 'gh-pages')
    apt_folder = os.environ.get('INPUT_REPO_FOLDER', 'repo')

    if None in (github_token, arch, version, deb_file):
        logging.error('Required key is missing')
        sys.exit(1)

    arch_list = arch.strip().split('\n')
    version_list = version.strip().split('\n')
    deb_file_list = deb_file.strip().split('\n')
    deb_file_version_list = deb_file_version.strip().split('\n')

    logging.debug(arch_list)
    logging.debug(version_list)
    logging.debug(deb_file_list)
    logging.debug(deb_file_version_list)

    if any((target_version not in version_list) for target_version in deb_file_version_list):
        logging.error('File version target is not listed in repo supported version list')
        sys.exit(1)

    key_public = os.environ.get('INPUT_PUBLIC_KEY')
    key_private = os.environ.get('INPUT_PRIVATE_KEY')
    key_passphrase = os.environ.get('INPUT_KEY_PASSPHRASE')

    logging.debug(github_token)
    logging.debug(arch_list)
    logging.debug(version_list)

    logging.info('-- Done parsing input --')

    # Clone repo

    logging.info('-- Cloning current Github page --')

    github_user = github_repo.split('/')[0]
    github_slug = github_repo.split('/')[1]

    if os.path.exists(github_slug):
        shutil.rmtree(github_slug)

    git_repo = git.Repo.clone_from(
        'https://{}@github.com/{}.git'.format(github_token, github_repo),
        github_slug,
        branch=gh_branch,
    )

    if git_repo.head.commit.message[:12] == '[apt-action]':
        logging.info('Loop detected, exiting')
        sys.exit(0)

    logging.info('-- Done cloning current Github page --')

    # Prepare key

    logging.info('-- Importing key --')

    key_dir = os.path.join(github_slug, 'public.key')
    gpg = gnupg.GPG()

    detectPublicKey(gpg, key_dir, key_public)
    private_key_id = importPrivateKey(gpg, key_private)

    logging.info('-- Done importing key --')

    # Prepare repo

    logging.info('-- Preparing repo directory --')

    apt_dir = os.path.join(github_slug, apt_folder)
    apt_conf_dir = os.path.join(apt_dir, 'conf')

    if not os.path.isdir(apt_folder):
        logging.info('Existing repo not detected, creating new repo')
        os.mkdir(apt_dir)
        os.mkdir(apt_conf_dir)

    logging.debug('Creating repo config')

    with open(os.path.join(apt_conf_dir, 'distributions'), "w") as distributions_file:
        for codename in version_list:
            distributions_file.write('Description: {}\n'.format(github_repo))
            distributions_file.write('Codename: {}\n'.format(codename))
            distributions_file.write('Architectures: {}\n'.format(' '.join(arch_list)))
            distributions_file.write('Components: main\n')
            distributions_file.write('SignWith: {}\n'.format(private_key_id))
            distributions_file.write('\n\n')

    logging.info('-- Done preparing repo directory --')

    # Fill repo

    logging.info('-- Adding package to repo --')

    for deb, target in zip(deb_file_list, deb_file_version_list):
        logging.info('Adding {}'.format(deb))
        os.system(
            'reprepro -b {} --export=silent-never includedeb {} {}'.format(
                apt_dir,
                target,
                deb,
            )
        )

    logging.debug('Signing to unlock key on gpg agent')
    gpg.sign('test', keyid=private_key_id, passphrase=key_passphrase)

    logging.debug('Export and sign repo')
    os.system('reprepro -b {} export'.format(apt_dir))

    logging.info('-- Done adding package to repo --')

    # Commiting and push changes

    logging.info('-- Saving changes --')

    git_repo.config_writer().set_value(
        'user', 'email', '{}@users.noreply.github.com'.format(github_user)
    )

    git_repo.git.add('*')
    git_repo.index.commit('[apt-action] Update apt repo')
    origin = git_repo.remote()
    origin.push()

    logging.info('-- Done saving changes --')
