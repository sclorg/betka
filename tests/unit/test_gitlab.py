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
import os

import pytest

from flexmock import flexmock

from betka.gitlab import GitLabAPI
from betka.constants import SYNCHRONIZE_BRANCHES
from betka.named_tuples import ProjectBranches, CurrentUser, ProjectMR
from betka.emails import BetkaEmails
from tests.conftest import (
    config_json,
    two_mrs_both_valid,
    two_mrs_not_valid,
    two_mrs_one_valid,
    gitlab_fork_exists,
)
from tests.spellbook import PROJECT_ID, PROJECT_ID_FORK


class TestBetkaGitlab(object):
    def betka_config(self):
        return {
            SYNCHRONIZE_BRANCHES: ["f3", "master"],
            "version": "1",
            "dist_git_repos": {
                "s2i-base": {
                    "url": "https://github.com/sclorg/s2i-base-container",
                    "project_id": PROJECT_ID,
                    "project_id_fork": PROJECT_ID_FORK,
                }
            },
            "gitlab_user": "foo_user",
            "downstream_master_msg": "[betka-master-sync]",
            "gitlab_api_token": "foobar",
        }

    def setup_method(self):
        os.environ["GITLAB_API_TOKEN"] = "foobar"
        self.ga = GitLabAPI(betka_config=self.betka_config(), config_json=config_json())
        self.ga.image = "s2i-base"
        self.ga.project_id = PROJECT_ID
        self.ga.set_variables(self.ga.image)

    def test_get_branches(self):
        flexmock(self.ga).should_receive("get_project_branches").and_return(
            ProjectBranches("rhel-8.6.0", "something", True),
            ProjectBranches("rhel-8.8.0", "something", True),
        )
        assert self.ga.get_branches() == ["rhel-8.6.0", "rhel-8.8.0"]

    @pytest.mark.parametrize(
        "project_mrs,branch,mr_id",
        [
            (two_mrs_both_valid(), "rhel-8.6.0", 2),
            (two_mrs_both_valid(), "rhel-8.8.0", 1),
            (two_mrs_both_valid(), "rhel-8.7.0", None),
        ],
    )
    def test_mrs_valid(self, project_mrs, branch, mr_id):
        flexmock(self.ga).should_receive("get_project_mergerequests").and_return(
            project_mrs
        )
        self.ga.betka_config = self.betka_config()
        assert self.ga.check_gitlab_merge_requests(branch=branch) == mr_id

    @pytest.mark.parametrize(
        "project_mr,branch,mr_id",
        [
            (two_mrs_not_valid(), "rhel-8.6.0", None),
            (two_mrs_not_valid(), "rhel-8.8.0", None),
            (two_mrs_not_valid(), "rhel-8.7.0", None),
        ],
    )
    def test_mrs_not_filed_by_betka(self, project_mr, branch, mr_id):
        flexmock(self.ga).should_receive("get_project_mergerequests").and_return(
            project_mr
        )
        self.ga.betka_config = self.betka_config()
        assert self.ga.check_gitlab_merge_requests(branch=branch) == mr_id

    def test_mrs_one_valid(self):
        flexmock(self.ga).should_receive("get_project_mergerequests").and_return(
            two_mrs_one_valid()
        )
        self.ga.betka_config = self.betka_config()
        assert self.ga.check_gitlab_merge_requests(branch="rhel-8.6.0") == 2

    @pytest.mark.parametrize(
        "host,namespace,image,branch,file,result_url",
        [
            (
                "https://src.fedoraproject.org",
                "containers",
                "postgresql",
                "",
                "bot-cfg.yml",
                "https://src.fedoraproject.org/containers/postgresql/-/raw//bot-cfg.yml",
            ),
            (
                "https://src.fedoraproject.org",
                "containers",
                "postgresql",
                "master",
                "foo-bar.yaml",
                "https://src.fedoraproject.org/containers/postgresql/-/raw/master/foo-bar.yaml",
            ),
            (
                "https://src.fedoraproject.org",
                "containers",
                "dummy-container",
                "f36",
                "foo-bar.yaml",
                "https://src.fedoraproject.org/containers/dummy-container/-/raw/f36/foo-bar.yaml",
            ),
        ],
    )
    def test_cfg_url(self, host, namespace, image, branch, file, result_url):
        self.ga.config_json["gitlab_host_url"] = host
        self.ga.config_json["gitlab_namespace"] = namespace
        self.ga.image = image

        assert result_url == self.ga.cfg_url(branch=branch, file=file)

    def test_valid_user(self):
        flexmock(self.ga).should_receive("check_authentication").and_return(
            CurrentUser(id=1234123, username="foo_user")
        )
        self.ga.betka_config = self.betka_config()
        assert self.ga.check_username()

    def test_missing_user(self):
        flexmock(self.ga).should_receive("check_authentication").and_return(None)
        flexmock(BetkaEmails).should_receive("send_email").once()
        self.ga.betka_config = self.betka_config()
        assert not self.ga.check_username()

    def test_wrong_resp_user(self):
        flexmock(self.ga).should_receive("check_authentication").and_return(
            CurrentUser(id=1234123, username="foobot")
        )
        flexmock(BetkaEmails).should_receive("send_email").once()
        self.ga.betka_config = self.betka_config()
        assert not self.ga.check_username()

    def test_file_merge_request_new(self):
        pr_msg = "Something"
        branch_name = "f34"
        mr_id = 12
        upstream_hash = "10938482734"
        flexmock(self.ga).should_receive("create_gitlab_merge_request").with_args(
            title="[betka-master-sync]", desc_msg=pr_msg, branch=branch_name
        ).and_return(
            ProjectMR(
                mr_id,
                "[betka-master-sync]",
                pr_msg,
                "rhel-8.6.0",
                "phracek",
                PROJECT_ID_FORK,
                PROJECT_ID,
                "https://gitlab/foo/bar",
            )
        )
        betka_schema = self.ga.file_merge_request(
            pr_msg=pr_msg, upstream_hash=upstream_hash, branch=branch_name, mr_id=None
        )
        assert betka_schema
        assert betka_schema["commit"] == upstream_hash
        assert betka_schema["mr_number"] is mr_id
        assert betka_schema["namespace_containers"] == "container"
        assert (
            betka_schema["downstream_repo"]
            == "https://github.com/sclorg/s2i-base-container"
        )
        assert betka_schema["status"] == "created"

    def test_file_merge_request_failed(self):
        pr_msg = "Something"
        branch_name = "f34"
        mr_id = None
        upstream_hash = "10938482734"
        flexmock(BetkaEmails).should_receive("send_email").once()
        flexmock(self.ga).should_receive("create_gitlab_merge_request").with_args(
            title="[betka-master-sync]", desc_msg=pr_msg, branch=branch_name
        ).and_return(mr_id)
        betka_schema = self.ga.file_merge_request(
            pr_msg=pr_msg, upstream_hash=upstream_hash, branch=branch_name, mr_id=mr_id
        )
        assert not betka_schema

    def test_file_merge_request_update(self):
        pr_msg = "Update"
        branch_name = "f35"
        mr_id = 13
        upstream_hash = "10938482734aeb"
        flexmock(self.ga).should_receive("create_gitlab_merge_request").with_args(
            title="[betka-master-sync]", desc_msg=pr_msg, branch=branch_name
        ).and_return(mr_id)
        betka_schema = self.ga.file_merge_request(
            pr_msg=pr_msg, upstream_hash=upstream_hash, branch=branch_name, mr_id=mr_id
        )
        assert betka_schema
        assert betka_schema["commit"] == upstream_hash
        assert betka_schema["mr_number"] is mr_id
        assert betka_schema["namespace_containers"] == "container"
        assert (
            betka_schema["downstream_repo"]
            == "https://github.com/sclorg/s2i-base-container"
        )
        assert betka_schema["status"] == "updated"

    def test_gitlab_fork(self):
        flexmock(self.ga).should_receive("get_project_forks").and_return(
            gitlab_fork_exists()
        )
        fork_exist = self.ga.get_gitlab_fork()
        assert fork_exist

    def test_gitlab_fork_is_missing(self):
        flexmock(self.ga).should_receive("get_project_forks").and_return([])
        fork_exist = self.ga.get_gitlab_fork()
        assert not fork_exist
