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


def bot_cfg_yaml_pr_checker():
    return {
        "enabled": True,
        "pr_checker": True,
        "upstream_git_path": "",
        "pr_comment_message": "[test]",
    }


def bot_cfg_yaml_master_checker():
    return {"enabled": True, "master_checker": True, "upstream_branch_name": "master"}


@pytest.fixture()
def mock_get_branches():
    flexmock(PagureAPI, _get_branches=["fc30", "fc31"])


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


def clone_git_repo(repo: Path, temp_dir: str) -> Path:
    return Git.clone_repo(str(repo), Path(temp_dir))
