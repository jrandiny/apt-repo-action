# Github pages APT repo

This action will setup and manage a simple APT repo on your github pages

## Inputs

### `github_token`

**Required** Personal access token with commit and push scope granted.

### `arch`

**Required** Newline-delimited list of supported architecture

### `version`

**Required** Newline-delimited list of supported (linux) version

### `file`

**Required** .deb files to be included

### `file_target_version`

**Required** Version target of supplied .deb file

### `private_key`

**Required** GPG private key for signing APT repo

### `public_key`

GPG public key for APT repo

### `key_passphrase`

Passphrase of GPG private key

### `page_branch`

Branch of Github pages. Defaults to `gh-pages`

### `repo_folder`

Location of APT repo folder relative to root of Github pages. Defaults to `repo`

## Example usage

```yaml
uses: jrandiny/apt-repo-action@v1
with:
  github_token: ${{ secrets.PAT }}
  arch: |
    amd64
    i386
  version: |
    bionic
    trusty
  file: my_program_bionic.deb
  file_target_version: bionic
  public_key: ${{ secrets.PUBLIC }}
  private_key: ${{ secrets.PRIVATE }}
  key_passphrase: ${{ secrets.SECRET }}
```