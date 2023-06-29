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
import pytest
import shlex
import subprocess
import json

from pathlib import Path
from tempfile import TemporaryDirectory

from tests.conftest import (
    betka_yaml,
    config_json,
    clone_git_repo,
    bot_cfg_yaml_master_checker,
    gitlab_fork_exists,
    gitlab_project_forks,
)
from betka.named_tuples import CurrentUser
from betka.gitlab import GitLabAPI
from betka.core import Betka
from betka.git import Git
from tests.spellbook import DATA_DIR


def _update_message(message):
    message["repository"]["html_url"] = "https://github.com/sclorg/s2i-base-container"
    message["repository"]["full_name"] = "sclorg/s2i-base-container"
    return message


@pytest.fixture()
def foo_bar_json():
    message = json.loads((DATA_DIR / "master_sync.json").read_text())
    message["repository"]["html_url"] = "https://github.com/foobar/foo"
    return message


@pytest.fixture()
def real_json():
    message = json.loads((DATA_DIR / "master_sync.json").read_text())
    return _update_message(message)


@pytest.fixture()
def wrong_branch():
    message = json.loads((DATA_DIR / "master_sync.json").read_text())
    message["ref"] = "not-master-based"
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
        os.environ["GITLAB_API_TOKEN"] = "gitlabsomething"
        os.environ["GITHUB_API_TOKEN"] = "aklsdjfh19p3845yrp"
        os.environ["GITLAB_USER"] = "testymctestface"
        self.betka = Betka(task_name="task.betka.master_sync")
        self.config_json = config_json()
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

    def fake_gitlab_fork(self):
        self.betka.gitlab_api.clone_url = str(self.downstream_repo / ".git")
        return True

    @pytest.fixture()
    def mock_git_clone(self):
        (flexmock(Git).should_receive("clone_repo").replace_with(self.fake_git_clone))

    @pytest.fixture()
    def mock_deploy(self):
        flexmock(self.betka, deploy_image=True)

    @pytest.fixture()
    def mock_get_gitlab_fork(self):
        (
            flexmock(self.betka.gitlab_api)
            .should_receive("get_gitlab_fork")
            .and_return(gitlab_fork_exists())
        )

    @pytest.fixture()
    def mock_get_project_forks(self):
        (
            flexmock(self.betka.gitlab_api)
            .should_receive("check_and_create_fork")
            .and_return(gitlab_project_forks())
        )

    @pytest.fixture()
    def mock_prepare_upstream(self):
        self.betka.upstream_cloned_dir = clone_git_repo(
            str(self.upstream_repo), str(self.betka.betka_tmp_dir.name)
        )
        (flexmock(self.betka).should_receive("prepare_upstream_git").and_return(True))

    @pytest.fixture()
    def mock_prepare_downstream(self):
        self.betka.downstream_dir = clone_git_repo(
            str(self.downstream_repo), str(self.betka.betka_tmp_dir.name)
        )
        (flexmock(self.betka).should_receive("prepare_downstream_git").and_return(True))

    @pytest.fixture()
    def mock_gitlab_bot_cfg_yaml(self):
        (
            flexmock(self.betka.gitlab_api)
            .should_receive("get_bot_cfg_yaml")
            .with_args(branch="fc30")
            .and_return(bot_cfg_yaml_master_checker())
        )

    @pytest.fixture()
    def init_betka_real_json(self, betka_config, real_json, mock_has_ssh_access):
        flexmock(self.betka.gitlab_api).should_receive(
            "check_authentication"
        ).and_return(CurrentUser(id=1234123, username="phracek"))
        assert self.betka.get_master_fedmsg_info(real_json)
        assert self.betka.betka_config.get("github_api_token") == "aklsdjfh19p3845yrp"
        assert self.betka.betka_config.get("gitlab_api_token") == "gitlabsomething"
        assert self.betka.prepare()

    def test_betka_wrong_url(self, betka_config, foo_bar_json):
        """Tests if betka doesn't include repos it's not supposed to include"""
        self.betka.betka_config["dist_git_repos"] = {}
        assert self.betka.get_master_fedmsg_info(foo_bar_json)
        assert self.betka.betka_config.get("github_api_token") == "aklsdjfh19p3845yrp"
        assert self.betka.betka_config.get("gitlab_api_token") == "gitlabsomething"
        assert self.betka.betka_config.get("gitlab_user") == "testymctestface"
        assert not self.betka.get_synced_images()

    def test_betka_non_master_push(self, wrong_branch):
        self.betka.betka_config["dist_git_repos"] = {}
        assert not self.betka.get_master_fedmsg_info(wrong_branch)

    def test_betka_master_sync(
        self,
        init_betka_real_json,
        mock_prepare_downstream,
        mock_prepare_upstream,
        mock_get_project_forks,
        mock_get_branches,
    ):
        list_images = self.betka.get_synced_images()
        sync_image = ""
        for key, value in list_images.items():
            sync_image = key
            break
        print(sync_image)
        self.betka.betka_config = betka_yaml()
        self.betka.gitlab_api.config = betka_yaml()
        self.betka.gitlab_api.set_variables(image=sync_image)
        assert self.betka.gitlab_api.check_and_create_fork()
        assert self.betka.downstream_dir
        flexmock(Git).should_receive("check_config_in_branch").with_args(
            downstream_dir=self.betka.downstream_dir, branch="fc31"
        ).and_return(True)
        flexmock(Git).should_receive("check_config_in_branch").with_args(
            downstream_dir=self.betka.downstream_dir, branch="fc30"
        ).and_return(False)
        os.chdir(str(self.betka.downstream_dir))
        branch_list = Git.get_valid_branches(
            image=sync_image,
            downstream_dir=self.betka.downstream_dir,
            branch_list=["fc31", "fc30"],
        )
        # only 'fc30' branch has the bot-cfg.yml file
        assert branch_list == ["fc31"]

    def test_betka_run_master_sync(
        self,
        init_betka_real_json,
        mock_get_gitlab_fork,
        mock_prepare_downstream,
        mock_prepare_upstream,
        mock_git_clone,
        mock_get_branches,
        mock_check_prs,
        mock_deploy,
        mock_rmtree,
    ):
        self.betka.betka_config["dist_git_repos"].pop("s2i-core")
        list_images = self.betka.get_synced_images()
        sync_image = ""
        for key, value in list_images.items():
            sync_image = key
            break
        self.betka.betka_config = betka_yaml()
        self.betka.gitlab_api.config = betka_yaml()
        self.betka.gitlab_api.set_variables(image=sync_image)
        flexmock(GitLabAPI).should_receive("init_projects").twice()
        flexmock(self.betka).should_receive("_update_valid_branches").and_return(
            ["fc30", "fc31"]
        )
        # flexmock(Git).should_receive("sync_fork_with_upstream").twice()
        self.betka.run_sync()

        # check if readme was updated (compare betka downstream vs test upstream)
        assert self.betka.downstream_dir
        os.chdir(str(self.betka.downstream_dir))
        Git.call_git_cmd("checkout fc31")
        upstream_readme = (self.upstream_repo / "README.md").read_text()
        downstream_readme = (self.betka.downstream_dir / "README.md").read_text()
        assert upstream_readme == downstream_readme

        # check git log
        latest_commit = Git.call_git_cmd("log -n 1 --format=medium")
        latest_commit = [x.strip() for x in latest_commit.split("\n") if x != ""]
        assert latest_commit
        assert latest_commit[3] == "Add bot-cfg.yml"

        # check the other branch - readme should be without the update, because the branch wasn't
        # configured with bot-cfg.yml
        Git.call_git_cmd("checkout fc30")

        # latest commit should be Init branch
        last_commit = Git.call_git_cmd("log -n 1 --format=medium")
        assert last_commit
        commit_fields = [x.strip() for x in last_commit.split("\n") if x.strip() != ""]
        assert commit_fields
        assert commit_fields[3] == "Init branch"
        assert commit_fields[4] == "For betka test"
        assert commit_fields[5] == "in fc30 branch"
