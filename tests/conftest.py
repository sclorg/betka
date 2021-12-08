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


import pytest
import sys
import shutil
from pathlib import Path
from flexmock import flexmock

from betka.core import Betka, GitHubAPI
from betka.git import Git
from betka.pagure import PagureAPI


def betka_yaml():
    return {
        "synchronize_branches": ["fc3"],
        "dist_git_repos": {
            "s2i-core": ["https://github.com/sclorg/s2i-base-container"]
        },
        "downstream_master_msg": "[betka-master-sync]",
        "downstream_pr_msg": "[betka-pr-sync]",
    }


def config_json():
    return {
        "api_url": "https://src.fedoraproject.org/api/0",
        "get_all_pr": "https://src.fedoraproject.org/api/0/{namespace}/{repo}/pull-requests",
        "git_url_repo": "https://src.fedoraproject.org/api/0/{fork_user}/{namespace}/{repo}/git/",
        "get_version_url": "https://src.fedoraproject.org/api/0/-/version",
        "namespace_containers": "container",
        "github_api_token": "GITHUB_API_TOKEN",
        "pagure_user": "PAGURE_USER",
        "pagure_api_token": "PAGURE_API_TOKEN",
        "betka_url_base": "foobar_url",
        "new_api_version": "true",
        "generator_url": "some_foo_generator",
    }


def config_json_api_not_supported():
    return {
        "api_url": "https://src.fedoraproject.org/api/0",
        "get_all_pr": "https://src.fedoraproject.org/api/0/{namespace}/{repo}/pull-requests",
        "git_url_repo": "https://src.fedoraproject.org/api/0/fork/{user}/{namespace}/{repo}/git/",
        "get_version_url": "https://src.fedoraproject.org/api/0/-/version",
        "namespace_containers": "container",
        "github_api_token": "GITHUB_API_TOKEN",
        "pagure_user": "PAGURE_USER",
        "pagure_api_token": "PAGURE_API_TOKEN",
        "betka_url_base": "foobar_url",
        "new_api_version": "false",
        "generator_url": "some_fob_bar_generator_url",
    }


def bot_cfg_yaml_pr_checker():
    return {
        "enabled": True,
        "pr_checker": True,
        "upstream_git_path": "",
        "pr_comment_message": "[test]",
    }


def no_pullrequest():
    return {
        "args": {
            "assignee": None,
            "author": None,
            "page": 1,
            "per_page": 20,
            "status": True,
            "tags": [],
        },
        "pagination": {
            "first": "https://src.fedoraproject.org/api/0/container/python3/"
            "pull-requests?per_page=20&page=1",
            "last": "https://src.fedoraproject.org/api/0/container/python3/"
            "pull-requests?per_page=20&page=0",
            "next": None,
            "page": 1,
            "pages": 0,
            "per_page": 20,
            "prev": None,
        },
        "requests": [],
        "total_requests": 0,
    }


def one_pullrequest():
    return {
        "args": {
            "assignee": None,
            "author": None,
            "page": 1,
            "per_page": 20,
            "status": True,
            "tags": [],
        },
        "pagination": {
            "first": "https://src.fedoraproject.org/api/0/container/httpd/"
            "pull-requests?per_page=20&page=1",
            "last": "https://src.fedoraproject.org/api/0/container/httpd/"
            "pull-requests?per_page=20&page=1",
            "next": None,
            "page": 1,
            "pages": 1,
            "per_page": 20,
            "prev": None,
        },
        "requests": [
            {
                "assignee": None,
                "branch": "f28",
                "branch_from": "f28",
                "cached_merge_status": "CONFLICTS",
                "closed_at": None,
                "closed_by": None,
                "comments": [
                    {
                        "comment": "Hi Marek, could you please remove RELEASE label from your "
                        "commit? (see https://src.fedoraproject.org/container/httpd"
                        "/c/5bfc9e82ed92ada2600a0e4bc59ef61ee42b39bf?branch=master )",
                        "commit": None,
                        "date_created": "1534862586",
                        "edited_on": None,
                        "editor": None,
                        "filename": None,
                        "id": 13853,
                        "line": None,
                        "notification": False,
                        "parent": None,
                        "reactions": {},
                        "tree": None,
                        "user": {"fullname": "Lubos Uhliarik", "name": "luhliarik"},
                    }
                ],
                "commit_start": "5870b2651d6b2aa69a82a84a9bd2ba9feb44c389",
                "commit_stop": "5870b2651d6b2aa69a82a84a9bd2ba9feb44c389",
                "date_created": "1534841326",
                "id": 5,
                "initial_comment": None,
                "last_updated": "1555582381",
                "project": {
                    "access_groups": {"admin": [], "commit": [], "ticket": []},
                    "access_users": {
                        "admin": ["luhliarik"],
                        "commit": ["jorton", "mskalick"],
                        "owner": ["hhorak"],
                        "ticket": [],
                    },
                    "close_status": [],
                    "custom_keys": [],
                    "date_created": "1501875660",
                    "date_modified": "1540562126",
                    "description": "The httpd container",
                    "fullname": "container/httpd",
                    "id": 24007,
                    "milestones": {},
                    "name": "httpd",
                    "namespace": "container",
                    "parent": None,
                    "priorities": {},
                    "tags": [],
                    "url_path": "container/httpd",
                    "user": {"fullname": "Honza Horak", "name": "hhorak"},
                },
                "remote_git": None,
                "repo_from": {
                    "access_groups": {"admin": [], "commit": [], "ticket": []},
                    "access_users": {
                        "admin": [],
                        "commit": [],
                        "owner": ["mskalick"],
                        "ticket": [],
                    },
                    "close_status": [],
                    "custom_keys": [],
                    "date_created": "1534840942",
                    "date_modified": "1534840942",
                    "description": "The httpd container",
                    "fullname": "forks/mskalick/container/httpd",
                    "id": 31905,
                    "milestones": {},
                    "name": "httpd",
                    "namespace": "container",
                    "parent": {
                        "access_groups": {"admin": [], "commit": [], "ticket": []},
                        "access_users": {
                            "admin": ["luhliarik"],
                            "commit": ["jorton", "mskalick"],
                            "owner": ["hhorak"],
                            "ticket": [],
                        },
                        "close_status": [],
                        "custom_keys": [],
                        "date_created": "1501875660",
                        "date_modified": "1540562126",
                        "description": "The httpd container",
                        "fullname": "container/httpd",
                        "id": 24007,
                        "milestones": {},
                        "name": "httpd",
                        "namespace": "container",
                        "parent": None,
                        "priorities": {},
                        "tags": [],
                        "url_path": "container/httpd",
                        "user": {"fullname": "Honza Horak", "name": "hhorak"},
                    },
                    "priorities": {},
                    "tags": [],
                    "url_path": "fork/mskalick/container/httpd",
                    "user": {"fullname": "Marek Skalický", "name": "mskalick"},
                },
                "status": "Open",
                "tags": [],
                "threshold_reached": None,
                "title": "[betka-master-sync]",
                "uid": "84a79e8ec53c4677b0ed99cfc10bff7f",
                "updated_on": "1534841326",
                "user": {"fullname": "Marek Skalický", "name": "foo"},
            }
        ],
        "total_requests": 1,
    }


def bot_cfg_yaml_master_checker():
    return {"enabled": True, "master_checker": True, "upstream_branch_name": "master"}


@pytest.fixture()
def mock_get_branches():
    flexmock(PagureAPI, get_branches=["fc30", "fc31"])


@pytest.fixture()
def mock_get_valid_branches():
    flexmock(PagureAPI, get_valid_branches=["fc30"])


@pytest.fixture()
def mock_has_ssh_access():
    flexmock(Git, has_ssh_access=True)


@pytest.fixture()
def mock_whois():
    flexmock(PagureAPI, get_user_from_token="mctestface")


@pytest.fixture()
def mock_check_prs():
    flexmock(PagureAPI, check_downstream_pull_requests=True)


@pytest.fixture()
def mock_send_email():
    # https://flexmock.readthedocs.io/en/latest/user-guide/#shorthand
    flexmock(sys.modules["betka.core"], send_email=None)


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
