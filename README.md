# Betka

[Travis-CI](https://travis-ci.org/sclorg/betka.svg?branch=master)

## Why Betka (name)?

Betka is a familar name for [Alžběta](https://cs.wikipedia.org/wiki/Al%C5%BEb%C4%9Bta) ([Elizabeth](https://en.wikipedia.org/wiki/Elizabeth) in English).
Betka is a nice lady you can meet at a local store or while walking a dog.
She's pleasant to talk to and is always smiling.

## What is Betka?

Betka syncs changes from upstream repository to downstream the way you ask her to
(e.g. whenever anything changes in upstream, or just specific commits).

### Betka main configuration file

Main betka's configuration file looks like:

```yaml
name: Fedora configuration file for betka.

dist_git_repos:
  s2i-base:
    - https://github.com/sclorg/s2i-base-container
  s2i-core:
    - https://github.com/sclorg/s2i-base-container
  python3:
    - https://github.com/sclorg/s2i-python-container

master_commit_message: "Upstream master commit hash {hash}"
downstream_master_msg: "[betka-master-sync]"
downstream_pr_msg: "[betka-pr-sync]"
```

where keys mean:
- `dist_git_repos` ... references to Fedora Pagure repositories, e.g. https://src.fedoraproject.org/container/s2i-base
- `upstream_check_interval` ... interval used for checking `master` upstream repository branches
- `downstream_master_msg` ... title message for PR related to master sync
- `downstream_pr_msg` ... title message for PR related to PR sync

### Betka downstream configuration file

Once betka is started, it loads specified downstream repositories and checks
if a branch used for syncing contains `bot-cfg.yml` configuration file.

This downstream configuration file looks like:

```yaml
version: "1"

upstream-to-downstream:
  # is betka enabled for this repository
  # optional - defaults to false
  enabled: true

  # optional
  notifications:
    email_addresses: [phracek@redhat.com]

  # Specify if master branch in upstream repository is synced
  master_checker: true
  # Should pull requests be synced?
  # optional
  pr_checker: false
  # Either 'upstream_branch_name' or 'upstream_git_path' has to be specified
  # Branch name which is used for sync
  upstream_branch_name: master
  # Path to directory with dockerfile withing upstream repository
  upstream_git_path: "2.4"
  # Github comment message to enforce sync of a pull request
  # required if pr_checker is true otherwise optional
  pr_comment_message: "[test]"
  # URL to an image used for dist-git source generation.
  # optional
  image_url: docker.io/rhscl/dist-git-generator

```

where keys mean:
- `enabled` ... if sync is enabled generally
- `master_checker` ... sync of master branch is enabled
- `pr_checker` ... sync of upstream pull requests is enabled
- `pr_comment_message` ... pull request message on which PR is synced into downstream PR
- `upstream_git_path` ... path to directory with dockerfile within upstream repository
- `upstream_branch_name` ... repository branch with dockerfile within upstream repository
- `image_url` ... docker image used for generation source into downstream repository.


## Betka's workflow
These are steps how betka works.
- loads main configuration file
- clones specific downstream repository
- checks if downstream branches, in dist-git repository, contain specific configuration file `bot-cfg.yml`
- parses `bot-cfg.yml` file and checks if some of checks like `master_checker` or `pr_checker` are allowed

### master_checker
- if `master_checker` is enabled, then it checks `master` upstream repository branch for new commits
    - clones upstream repository in case of new commit and configuration file contains `master_checker` flag
    - syncs files from upstream into downstream specific branch
    - fills a pull request into Internal Pagure instance `src.fedoraproject.org` if pull request does not exist yet
    - updates specific pull request in Internal Pagure instance

### pr_checker
- if `pr_checker` is enabled, then it checks all pull requests in upstream repository
    - syncs files from upstream into downstream specific branch
    - clones upstream repository in case of new commit and configuration file contains `pr_checker` flag
    - If specific downstream pull request does not exist yet, then it's created from the upstream pull request
    - If specific downstream pull request already exists, then it's updated

## Requirements

In order to run betka, some requirements are needed:
- `Pagure API token` ... for creating Pull Request and working with repositories.
Get the token from https://src.fedoraproject.org/settings#nav-basic-tab
- `GitHub API token` ... for getting information from upstream repositories.
Get the token from https://github.com/settings/tokens

For local development we use docker-compose, so you have to install it first.
Its configuration file, [docker-compose.yml](docker-compose.yml), sources `secrets.env`.
There's a [secrets.env.template](secrets.env.template) file, which you have to copy to `secrets.env`
and fill in the values there!

## How to start betka

```
make run
```

Your SSH keys (`${HOME}/.ssh/*`) will be mounted to `/home/betka/.ssh` directory inside container.

## How to test betka locally in OpenShift (this is outdated, needs update)

In order to run betka locally, some requirements are needed:
- package `origin-clients` has to be installed, if image configuration file contains variable `image_url`
- build image with `make build`
- tag image with `docker tag docker.io/rhscl/betka docker.io/rhscl/betka:git-HASH` (use random HASH)
- update image tag in `openshift/old/tpl-betka-deployment.yaml` with HASH
- run command `make oc-cluster-up-and-deploy` as root or with sudo command
    - starts OpenShift cluster locally
    - adds ServiceAccount and RoleBindings
- Now start tests by command: `py.test-3 tests/test_openshift_pod.py`

See also [bots-deployment](https://github.com/user-cont/bots-deployment) repo.

## User guide for image maintainers

1. You need to contact us for adding your repository to the configuration of our instance of Betka.
    - You can directly create PR with proper changes in
    [betka.yaml](https://github.com/sclorg/betka/blob/master/betka-prod.yaml),
    see [this section](https://github.com/sclorg/betka#betka-main-configuration-file) for more information.
    - or you can contact us via `phracek@redhat.com` mailing list.
2. Your upstream repository needs to have [fedmsg](https://github.com/fedora-infra/github2fedmsg) enabled.
3. You need to have correct [bot-cfg.yml](https://github.com/sclorg/betka#betka-downstream-configuration-file)
in your downstream repository.

### Source generator used by betka
If you need to generate the sources for the downstream repository,
use your own source generation image, which you are responsible for.
Betka provides two variables into your own source generation image:
- `DOWNSTREAM_IMAGE_NAME` ... needed for `cwt` tool developed by SCL team
(https://github.com/sclorg/container-workflow-tool) which is responsible for downstream sources generation.
- `UPSTREAM_IMAGE_NAME` ... upstream sources name.`

The upstream sources in your image are stored in `/tmp/betka-generator/<UPSTREAM_IMAGE_NAME>`.
E.g. `/tmp/betka-generator/mariadb-container` from https://github.com/sclorg/mariadb-container.

Generated sources to sync to downstream are then stored in `/tmp/betka-generator/<timestamp>/results`.
