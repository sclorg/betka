"""Test betka core class"""

from flexmock import flexmock
import os
from pathlib import Path
import pytest
import shlex
import subprocess
from tempfile import TemporaryDirectory

from betka.core import Betka
from betka.git import Git
from betka.umb import UMBSender
from tests.conftest import clone_git_repo, bot_cfg_yaml_pr_checker


MESSAGE = "Update 10.2 fedora dockerfile for f28"


@pytest.fixture()
def foo_bar_json():
    message = {
        "repository": {
            "full_name": "foobar/foo",
            "html_url": "https://github.com/sclorg/s2i-base-container",
        },
        "comment": {"body": "[test]", "id": 1},
        "issue": {
            "number": "1",
            "id": 1,
            "title": "Update FOOBAR",
            "user": {"login": "foofigter"},
            "pull_request": {
                "url": "https://github.com/foobar/foo/pulls/1",
                "html_url": "https://github.com/foobar/foo/pull/1",
            },
        },
    }
    return message


@pytest.fixture()
def real_json():
    message = {
        "repository": {
            "full_name": "foobar/foo",
            "html_url": "https://github.com/sclorg/s2i-base-container",
        },
        "comment": {"body": "[test]", "id": 1},
        "issue": {
            "number": "1",
            "id": 1,
            "title": "Update README",
            "user": {"login": "foofigter"},
            "pull_request": {
                "url": "https://api.github.com/repos/sclorg/s2i-base-container/pulls/1",
                "html_url": "https://github.com/sclorg/s2i-base-container/pull/1",
            },
        },
        "ref": "refs/heads/master",
    }
    return message


class TestBetkaPrSync(object):
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
        self.github = "aklsdjfh19p3845yrp"
        self.pagure_user = "testymctestface"
        os.environ["GITHUB_API_TOKEN"] = self.github
        os.environ["PAGURE_API_TOKEN"] = "testing"
        os.environ["PAGURE_USER"] = self.pagure_user
        self.betka = Betka(task_name="task.betka.pr_sync")
        self.betka.set_config()
        self.tmpdir = TemporaryDirectory()
        self.upstream_repo = Path(self.tmpdir.name) / "upstream"
        self.downstream_repo = Path(self.tmpdir.name) / "downstream"
        assert self._run_cmd(
            f"./setup_upstream_downstream.sh "
            f"{self.upstream_repo} {self.downstream_repo}",
            Path(__file__).parent / "src/",
        )

    def fake_pagure_fork(self):
        self.betka.pagure_api.clone_url = str(self.downstream_repo / ".git")
        return True

    def fake_git_clone(self, clone_url, tempdir):
        repodir = Git.strip_dot_git(clone_url.split("/")[-2])
        Git.call_git_cmd(
            "clone --recurse-submodules {u} {d}".format(
                u=clone_url, d=os.path.join(tempdir, repodir)
            ),
            msg=clone_url,
        )
        return os.path.join(tempdir, repodir)

    @pytest.fixture()
    def mock_deploy(self):
        flexmock(self.betka, deploy_image=True)

    @pytest.fixture()
    def mock_get_pagure_fork(self):
        (
            flexmock(self.betka.pagure_api)
            .should_receive("get_pagure_fork")
            .replace_with(self.fake_pagure_fork)
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
    def mock_get_bot_cfg_yaml(self):
        (
            flexmock(Betka)
            .should_receive("_get_bot_cfg")
            .with_args(branch="fc30")
            .and_return(True)
        )

    @pytest.fixture()
    def mock_git_clone(self):
        (flexmock(Git).should_receive("clone_repo").replace_with(self.fake_git_clone))

    @pytest.fixture()
    def init_betka_real_json(
        self, mock_whois, betka_config, real_json, mock_has_ssh_access
    ):
        assert self.betka.get_pr_fedmsg_info(real_json)
        assert self.betka.prepare()

    def test_betka_wrong_url(self, betka_config, foo_bar_json):
        """Tests if betka doesn't include repos it's not supposed to include"""
        self.betka.betka_config["dist_git_repos"] = {}
        assert self.betka.get_pr_fedmsg_info(foo_bar_json)
        self.betka.set_config()
        assert self.betka.betka_config.get("github_api_token") == self.github
        assert self.betka.betka_config.get("pagure_user") == self.pagure_user
        assert not self.betka.get_synced_images()

    def test_betka_valid_branches(
        self,
        init_betka_real_json,
        mock_prepare_downstream,
        mock_get_pagure_fork,
        mock_get_branches,
    ):
        synced_image = self.betka.get_synced_images()[0]
        assert synced_image
        self.betka.set_config()
        assert self.betka.betka_config["pagure_user"]
        assert self.betka.pagure_api.get_pagure_fork()
        self.betka.clone_url = self.betka.pagure_api.get_clone_url()
        self.betka.pagure_api.betka_config = self.betka.betka_config
        assert self.betka.clone_url
        self.betka.prepare_downstream_git()
        assert self.betka.downstream_dir
        flexmock(self.betka.pagure_api).should_receive(
            "check_config_in_branch"
        ).with_args(downstream_dir=self.betka.downstream_dir, branch="fc31").and_return(
            True
        )
        flexmock(self.betka.pagure_api).should_receive(
            "check_config_in_branch"
        ).with_args(downstream_dir=self.betka.downstream_dir, branch="fc30").and_return(
            False
        )
        os.chdir(str(self.betka.downstream_dir))
        branch_list = self.betka.pagure_api.get_valid_branches(
            Path(self.betka.downstream_dir), branch_list=["fc30", "fc31"]
        )
        # only 'fc31' branch has the bot-cfg.yml file
        assert branch_list == ["fc31"]

    def test_betka_run_pr_closed(
        self,
        init_betka_real_json,
        mock_get_pagure_fork,
        mock_prepare_downstream,
        mock_prepare_upstream,
        mock_git_clone,
        mock_get_valid_branches,
        mock_get_bot_cfg_yaml,
        mock_get_branches,
        mock_send_email,
        mock_rmtree,
        mock_check_upstream_pr_closed,
    ):
        self.betka.betka_config["dist_git_repos"].pop("s2i-core")
        self.betka.config = bot_cfg_yaml_pr_checker()
        flexmock(UMBSender).should_receive(
            "send_umb_message_in_progress"
        ).and_return().once()
        flexmock(UMBSender).should_receive("send_umb_message_error").never()
        self.betka.run_sync()

    def test_betka_run_pr_sync(
        self,
        init_betka_real_json,
        mock_get_pagure_fork,
        mock_prepare_downstream,
        mock_prepare_upstream,
        mock_git_clone,
        mock_get_valid_branches,
        mock_get_bot_cfg_yaml,
        mock_deploy,
        mock_fetch_pr_origin,
        mock_check_upstream_pr_opened,
        mock_check_prs,
        mock_send_email,
        mock_rmtree,
    ):
        self.betka.set_config()
        assert self.betka.betka_config["pagure_user"]
        self.betka.betka_config["dist_git_repos"].pop("s2i-core")
        self.betka.pagure_api.config = self.betka.betka_config
        self.betka.config = bot_cfg_yaml_pr_checker()
        flexmock(UMBSender).should_receive(
            "send_umb_message_in_progress"
        ).and_return().once()
        flexmock(UMBSender).should_receive("send_umb_message_error").never()
        self.betka.run_sync()
        assert self.betka.downstream_dir
