import os
import sys
import logging
import gnupg
import git
import shutil

debug = os.environ.get('INPUT_DEBUG')

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

    pub_key = os.environ.get('INPUT_PUBLIC_KEY')
    sign_key = os.environ.get('INPUT_PRIVATE_KEY')
    secret = os.environ.get('INPUT_KEY_SECRET')

    logging.debug(github_token)
    logging.debug(arch_list)
    logging.debug(version_list)

    logging.info('-- Done parsing input --')

    logging.info('-- Cloning current repo --')

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

    logging.info('-- Importing key --')

    logging.info('Detecting public key')

    logging.debug('Detecting existing public key')

    key_dir = os.path.join(github_slug, 'public.key')
    key_exists = os.path.isfile(key_dir)

    logging.debug('Existing public key file exists? {}'.format(key_exists))

    gpg = gnupg.GPG()

    if not key_exists:
        logging.info('Directory doesn\'t contain public.key trying to import')
        if pub_key is None:
            logging.error('Please specify public key for setup')
            sys.exit(1)

        logging.debug('Trying to import key')

        public_import_result = gpg.import_keys(pub_key)
        public_import_result.ok_reason

        logging.debug(public_import_result)

        if public_import_result.count != 1:
            logging.error('Invalid public key provided, please provide 1 valid key')
            sys.exit(1)

        with open(key_dir, 'w') as key_file:
            key_file.write(pub_key)

    logging.info('Public key valid')

    logging.info('Importing private key')

    private_import_result = gpg.import_keys(sign_key)

    if private_import_result.count != 1:
        logging.error('Invalid private key provided, please provide 1 valid key')
        sys.exit(1)

    logging.debug(private_import_result)

    if not any(data['ok'] >= '16' for data in private_import_result.results):
        logging.error('Key provided is not a secret key')
        sys.exit(1)

    private_key_id = private_import_result.results[0]['fingerprint']

    logging.info('Private key valid')

    logging.debug('Key id: {}'.format(private_key_id))

    logging.info('-- Done importing key --')

    logging.info('-- Preparing repo directory --')

    apt_dir = os.path.join(github_slug, apt_folder)

    apt_conf_dir = os.path.join(apt_dir, 'conf')

    if not os.path.isdir(apt_folder):
        logging.debug('Existing repo not detected, creating new repo')
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

    logging.info('-- Adding package to repo --')

    for deb, target in zip(deb_file_list, deb_file_version_list):
        os.system(
            'reprepro -b {} --export=silent-never includedeb {} {}'.format(
                apt_dir,
                target,
                deb,
            )
        )

    gpg.sign('test', keyid=private_key_id, passphrase=secret)

    os.system('reprepro -b {} export'.format(apt_dir))

    logging.info('-- Done adding package to repo --')

    logging.info('-- Saving changes --')

    git_repo.config_writer().set_value(
        'user', 'email', '{}@users.noreply.github.com'.format(github_user)
    )

    git_repo.git.add('*')
    git_repo.index.commit('[apt-action] Update apt repo')
    origin = git_repo.remote()
    origin.push()

    logging.info('-- Done saving changes --')
