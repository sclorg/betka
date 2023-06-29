# MIT License
#
# Copyright (c) 2020 SCL team at Red Hat
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
import json

import pytest
import shutil
from pathlib import Path
from flexmock import flexmock


from tests.spellbook import DATA_DIR, PROJECT_ID, PROJECT_ID_FORK

from betka.emails import BetkaEmails
from betka.core import Betka, GitHubAPI
from betka.git import Git
from betka.gitlab import GitLabAPI
from betka.named_tuples import ProjectMRs, ProjectFork


def betka_yaml():
    return {
        "synchronize_branches": ["fc3"],
        "dist_git_repos": {
            "s2i-core": {
                "url": "https://github.com/sclorg/s2i-base-container",
                "project_id": 12,
                "project_id_fork": 21,
            },
            "s2i-base": {
                "url": "https://github.com/sclorg/s2i-base-container",
                "project_id": 23,
                "project_id_fork": 32,
            },
            "postgresql": {
                "url": "https://github.com/sclorg/postgresql-container",
                "project_id": 34,
            },
            "nodejs-10": {
                "url": "https://github.com/sclorg/s2i-nodejs-container",
                "project_id": 45,
            },
            "nginx-container": {
                "url": "https://github.com/sclorg/nginx-container",
                "project_id": 56,
            },
        },
        "downstream_master_msg": "[betka-master-sync]",
    }


def config_json():
    return {
        "api_url": "https://src.fedoraproject.org/api/0",
        "get_all_pr": "https://src.fedoraproject.org/api/0/{namespace}/{repo}/pull-requests",
        "git_url_repo": "https://src.fedoraproject.org/api/0/{fork_user}/{namespace}/{repo}/git/",
        "get_version_url": "https://src.fedoraproject.org/api/0/-/version",
        "namespace_containers": "container",
        "github_api_token": "GITHUB_API_TOKEN",
        "gitlab_api_token": "GITLAB_API_TOKEN",
        "gitlab_user": "GITLAB_USER",
        "betka_url_base": "foobar_url",
        "generator_url": "some_foo_generator",
        "gitlab_api_url": "https://gitlab.com/api/v4/",
        "gitlab_list_mr": "projects/{id}/merge_requests?state=opened",
        "gitlab_branches": "projects/{id}/repository/branches",
        "gitlab_forks": "projects/{id}/forks",
        "gitlab_fork_project": "projects/{id}/fork",
        "gitlab_access_request": "projects/{id}/access_requests",
        "gitlab_create_merge_request": "projects/{id}/merge_requests",
        "gitlab_host_url": "https://gitlab.com/",
        "gitlab_url_user": "user",
        "slack_webhook_url": "SLACK_WEBHOOK_URL",
    }


def config_json_api_not_supported():
    return {
        "api_url": "https://src.fedoraproject.org/api/0",
        "get_all_pr": "https://src.fedoraproject.org/api/0/{namespace}/{repo}/pull-requests",
        "git_url_repo": "https://src.fedoraproject.org/api/0/fork/{user}/{namespace}/{repo}/git/",
        "get_version_url": "https://src.fedoraproject.org/api/0/-/version",
        "namespace_containers": "container",
        "github_api_token": "GITHUB_API_TOKEN",
        "gitlab_api_token": "GITLAB_API_TOKEN",
        "betka_url_base": "foobar_url",
        "generator_url": "some_fob_bar_generator_url",
    }


def bot_cfg_yaml_pr_checker():
    return {
        "enabled": True,
        "pr_checker": True,
        "upstream_git_path": "",
        "pr_comment_message": "[test]",
    }


def get_user_valid():
    return json.loads((DATA_DIR / "get_user_info_valid.json").read_text())


def get_missing_user_valid():
    return json.loads((DATA_DIR / "get_missing_user.json").read_text())


def branches_list_full():
    return json.loads((DATA_DIR / "branches_list.json").read_text())


def create_gitlab_fork():
    return json.loads((DATA_DIR / "create_gitlab_fork.json").read_text())


def project_mrs():
    return [
        ProjectMRs(2, PROJECT_ID, "rhel-8.6.0", "[betka-master-sync]", "phracek"),
        ProjectMRs(1, PROJECT_ID, "rhel-8.8.0", "[betka-master-sync]", "phracek"),
        ProjectMRs(3, PROJECT_ID, "rhel-8.6.0", "[betka-master-sync]", "phracek"),
    ]


def two_mrs_both_valid():
    return [
        ProjectMRs(2, PROJECT_ID, "rhel-8.6.0", "[betka-master-sync]", "phracek"),
        ProjectMRs(1, PROJECT_ID, "rhel-8.8.0", "[betka-master-sync]", "phracek"),
        ProjectMRs(3, PROJECT_ID, "rhel-8.6.0", "[betka-master-sync]", "phracek"),
    ]


def two_mrs_not_valid():
    return [
        ProjectMRs(
            2, PROJECT_ID, "rhel-8.6.0", "Add TMT/TFT testing plan for CI", "phracek"
        ),
        ProjectMRs(1, PROJECT_ID, "rhel-8.6.0", "Testing commit", "hhorak"),
    ]


def two_mrs_one_valid():
    return [
        ProjectMRs(2, PROJECT_ID, "rhel-8.6.0", "[betka-master-sync]", "phracek"),
        ProjectMRs(1, PROJECT_ID, "rhel-8.8.0", "title", "hhorak"),
    ]


def gitlab_fork_exists():
    return ProjectFork(
        id=PROJECT_ID_FORK,
        name="nodejs-10",
        ssh_url_to_repo="git@gitlab.com:foo/bar.git",
        username="foo_user",
        forked_from_id=PROJECT_ID,
        forked_ssh_url_to_repo="git@gitlab.com:redhat/some/foor/bar.git",
    )


def gitlab_another_fork():
    return ProjectFork(
        id=PROJECT_ID_FORK,
        name="nodejs-10",
        ssh_url_to_repo="git@gitlab.com:foo/bar.git",
        username="foo_user",
        forked_from_id=PROJECT_ID,
        forked_ssh_url_to_repo="git@gitlab.com:redhat/some/foor/bar.git",
    )


def gitlab_project_forks():
    return ProjectFork(
        id=12,
        name="s2i-core",
        ssh_url_to_repo="git@gitlab.com:foo/bar.git",
        username="foo_user",
        forked_from_id=PROJECT_ID,
        forked_ssh_url_to_repo="git@gitlab.com:redhat/some/foor/bar.git",
    )


def bot_cfg_yaml_master_checker():
    return {"enabled": True, "master_checker": True, "upstream_branch_name": "master"}


@pytest.fixture()
def mock_get_branches():
    flexmock(GitLabAPI, get_branches=["fc30", "fc31"])


@pytest.fixture()
def mock_get_valid_branches():
    flexmock(Git, get_valid_branches=["fc30"])


@pytest.fixture()
def mock_has_ssh_access():
    flexmock(Git, has_ssh_access=True)


# @pytest.fixture()
# def mock_whois():
#     flexmock(GitLabAPI, get_user_from_token="mctestface")


@pytest.fixture()
def mock_check_prs():
    flexmock(GitLabAPI, check_gitlab_merge_requests=True)


@pytest.fixture()
def mock_send_email():
    # https://flexmock.readthedocs.io/en/latest/user-guide/#shorthand
    flexmock(BetkaEmails).should_receive("send_email").once()


@pytest.fixture()
def mock_check_upstream_pr_closed():
    flexmock(GitHubAPI, check_upstream_pr="CLOSED")


@pytest.fixture()
def mock_check_upstream_pr_opened():
    flexmock(GitHubAPI, check_upstream_pr="OPEN")


@pytest.fixture()
def mock_rmtree():
    flexmock(shutil, rmtree=True)


@pytest.fixture()
def mock_fetch_pr_origin():
    flexmock(Git, fetch_pr_origin=True)


@pytest.fixture()
def betka_config():
    (flexmock(Betka).should_receive("get_betka_yaml_config").replace_with(betka_yaml))


def clone_git_repo(repo: str, temp_dir: str) -> Path:
    return Git.clone_repo(repo, temp_dir)
