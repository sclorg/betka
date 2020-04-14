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

"""Test betka core class"""

from flexmock import flexmock
import os
from pathlib import Path
import pytest
import shlex
import subprocess
import json

from tests.conftest import (
    betka_yaml,
    clone_git_repo,
    bot_cfg_yaml_master_checker,
    mock_get_branches,
    mock_check_prs,
    mock_send_email,
    mock_rmtree,
)
from tempfile import TemporaryDirectory

from betka.core import Betka
from betka.git import Git
from betka.umb import UMBSender
from tests.spellbook import DATA_DIR


MESSAGE = "Add bot-cfg.yml"


def _update_message(message):
    message["msg"]["repository"][
        "html_url"
    ] = "https://github.com/sclorg/s2i-base-container"
    message["msg"]["repository"]["full_name"] = "sclorg/s2i-base-container"
    return message


@pytest.fixture()
def foo_bar_json():
    message = json.loads((DATA_DIR / "master_sync.json").read_text())
    message["msg"]["repository"]["html_url"] = "https://github.com/foobar/foo"
    return message


@pytest.fixture()
def real_json():
    message = json.loads((DATA_DIR / "master_sync.json").read_text())
    return _update_message(message)


@pytest.fixture()
def wrong_branch():
    message = json.loads((DATA_DIR / "master_sync.json").read_text())
    message["msg"]["ref"] = "not-master-based"
    return _update_message(message)


class TestBetkaMasterSync(object):
    def _run_cmd(self, cmd, work_directory):
        shell = subprocess.run(
            shlex.split(cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            cwd=work_directory,
            universal_newlines=True,
        )
        if shell.returncode == 0:
            return True
        return False

    def setup_method(self):
        self.betka = Betka()
        self.github = "aklsdjfh19p3845yrp"
        self.pagure_user = "testymctestface"
        os.environ["GITHUB_API_TOKEN"] = self.github
        os.environ["PAGURE_API_TOKEN"] = "testing"
        os.environ["PAGURE_USER"] = self.pagure_user
        self.betka.set_config()
        self.tmpdir = TemporaryDirectory()
        self.upstream_repo = Path(self.tmpdir.name) / "upstream"
        self.downstream_repo = Path(self.tmpdir.name) / "downstream"
        assert self._run_cmd(
            f"./setup_upstream_downstream.sh "
            f"{self.upstream_repo} {self.downstream_repo}",
            Path(__file__).parent / "src/",
        )

    def fake_git_clone(self, clone_url, tempdir):
        repodir = Git.strip_dot_git(clone_url.split("/")[-2])
        Git.call_git_cmd(
            "clone --recurse-submodules {u} {d}".format(
                u=clone_url, d=os.path.join(tempdir, repodir)
            ),
            msg=clone_url,
        )
        return os.path.join(tempdir, repodir)

    def fake_pagure_fork(self):
        self.betka.pagure_api.clone_url = str(self.downstream_repo / ".git")
        return True

    @pytest.fixture()
    def mock_git_clone(self):
        (flexmock(Git).should_receive("clone_repo").replace_with(self.fake_git_clone))

    @pytest.fixture()
    def mock_deploy(self):
        flexmock(self.betka, deploy_image=True)

    @pytest.fixture()
    def mock_get_pagure_fork(self):
        (
            flexmock(self.betka.pagure_api)
            .should_receive("get_pagure_fork")
            .and_return(self.fake_pagure_fork())
        )

    @pytest.fixture()
    def mock_prepare_upstream(self):
        self.betka.upstream_cloned_dir = clone_git_repo(
            self.upstream_repo, self.betka.betka_tmp_dir.name
        )
        (flexmock(self.betka).should_receive("prepare_upstream_git").and_return(True))

    @pytest.fixture()
    def mock_prepare_downstream(self):
        self.betka.downstream_dir = clone_git_repo(
            self.downstream_repo, self.betka.betka_tmp_dir.name
        )
        (flexmock(self.betka).should_receive("prepare_downstream_git").and_return(True))

    @pytest.fixture()
    def mock_pagure_bot_cfg_yaml(self):
        (
            flexmock(self.betka.pagure_api)
            .should_receive("get_bot_cfg_yaml")
            .with_args(branch="fc30")
            .and_return(bot_cfg_yaml_master_checker())
        )

    @pytest.fixture()
    def init_betka_real_json(
        self, mock_whois, betka_config, real_json, mock_has_ssh_access
    ):
        assert self.betka.get_master_fedmsg_info(real_json)
        assert self.betka.prepare()

    def test_betka_wrong_url(self, betka_config, foo_bar_json):
        """Tests if betka doesn't include repos it's not supposed to include"""
        self.betka.betka_config["dist_git_repos"] = {}
        assert self.betka.get_master_fedmsg_info(foo_bar_json)
        assert self.betka.betka_config.get("github_api_token") == self.github
        assert self.betka.betka_config.get("pagure_user") == self.pagure_user
        assert not self.betka.get_synced_images()

    def test_betka_non_master_push(self, wrong_branch):
        self.betka.betka_config["dist_git_repos"] = {}
        assert not self.betka.get_master_fedmsg_info(wrong_branch)

    def test_betka_master_sync(
        self,
        init_betka_real_json,
        mock_prepare_downstream,
        mock_prepare_upstream,
        mock_get_pagure_fork,
        mock_get_branches,
    ):
        synced_image = self.betka.get_synced_images()[0]
        assert synced_image
        self.betka.betka_config = betka_yaml()
        self.betka.pagure_api.config = betka_yaml()
        self.betka.pagure_api.set_image(synced_image)

        assert self.betka.pagure_api.get_pagure_fork()
        self.betka.clone_url = self.betka.pagure_api.get_clone_url()
        assert self.betka.clone_url
        assert self.betka.downstream_dir
        os.chdir(str(self.betka.downstream_dir))
        branch_list = self.betka.pagure_api.get_valid_branches(
            self.betka.downstream_dir
        )
        # only 'fc30' branch has the bot-cfg.yml file
        assert branch_list == ["fc31"]

    def test_betka_run_master_sync(
        self,
        init_betka_real_json,
        mock_get_pagure_fork,
        mock_prepare_downstream,
        mock_prepare_upstream,
        mock_git_clone,
        mock_get_branches,
        mock_check_prs,
        mock_deploy,
        mock_send_email,
        mock_rmtree,
    ):
        self.betka.betka_config["dist_git_repos"].pop("s2i-core")
        flexmock(UMBSender).should_receive(
            "send_umb_message_in_progress"
        ).and_return().once()
        flexmock(UMBSender).should_receive("send_umb_message_error").never()
        self.betka.run_sync()

        # check if readme was updated (compare betka downstream vs test upstream)
        assert self.betka.downstream_dir
        os.chdir(str(self.betka.downstream_dir))
        Git.call_git_cmd("checkout fc31")
        upstream_readme = (self.upstream_repo / "README.md").read_text()
        downstream_readme = (self.betka.downstream_dir / "README.md").read_text()
        assert upstream_readme == downstream_readme

        # check git log
        latest_commit = Git.call_git_cmd("log -n 1 --format=%s ")
        assert latest_commit.startswith(MESSAGE)

        # check the other branch - readme should be without the update, because the branch wasn't
        # configured with bot-cfg.yml
        Git.call_git_cmd("checkout fc30")

        # latest commit should be Init branch
        assert Git.call_git_cmd("log -n 1 --format=%s") == "Init branch\n"
