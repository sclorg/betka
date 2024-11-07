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
import requests
import pytest

from flexmock import flexmock
from requests.exceptions import HTTPError

from betka.gitlab import GitLabAPI
from betka.constants import SYNCHRONIZE_BRANCHES
from betka.named_tuples import ProjectBranches, ForkProtectedBranches, CurrentUser, ProjectMR
from betka.emails import BetkaEmails
from tests.conftest import (
    config_json,
    two_mrs_both_valid,
    two_mrs_not_valid,
    two_mrs_one_valid,
    gitlab_fork_exists,
    gitlab_another_fork,
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
                }
            },
            "gitlab_user": "foo_user",
            "downstream_master_msg": "[betka-master-sync]",
            "gitlab_api_token": "foobar",
            "gitlab_namespace": "foo_namespace",
            "dist_git_url": "https://src.fedoraproject.org/containers"
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
        flexmock(self.ga).should_receive("get_target_protected_branches").and_return([])
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
        mr = self.ga.check_gitlab_merge_requests(branch=branch, target_branch=branch)
        if mr_id:
            assert mr.iid == mr_id
            assert mr.target_branch == branch
        else:
            assert not mr

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
        assert self.ga.check_gitlab_merge_requests(branch=branch, target_branch=branch) == mr_id

    def test_mrs_one_valid(self):
        flexmock(self.ga).should_receive("get_project_mergerequests").and_return(
            two_mrs_one_valid()
        )
        self.ga.betka_config = self.betka_config()
        mr = self.ga.check_gitlab_merge_requests(branch="rhel-8.6.0", target_branch="rhel-8.6.0")
        assert mr.iid == 2
        assert mr.target_branch == "rhel-8.6.0"

    @pytest.mark.parametrize(
        "host,namespace,image,branch,file,result_url",
        [
            (
                "https://src.fedoraproject.org/containers",
                "containers",
                "postgresql",
                "",
                "bot-cfg.yml",
                "https://src.fedoraproject.org/containers/postgresql/plain/bot-cfg.yml?h=",
            ),
            (
                "https://src.fedoraproject.org/containers",
                "containers",
                "postgresql",
                "master",
                "foo-bar.yaml",
                "https://src.fedoraproject.org/containers/postgresql/plain/foo-bar.yaml?h=master",
            ),
            (
                "https://src.fedoraproject.org/containers",
                "containers",
                "dummy-container",
                "f36",
                "foo-bar.yaml",
                "https://src.fedoraproject.org/containers/dummy-container/plain/foo-bar.yaml?h=f36",
            ),
        ],
    )
    def test_cfg_url(self, host, namespace, image, branch, file, result_url):
        self.ga.config_json["dist_git_url"] = host
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
        mr = ProjectMR(
            mr_id, "[betka-master-sync]", pr_msg,
            "rhel-8.6.0", "phracek", PROJECT_ID_FORK, PROJECT_ID, "https://gitlab/foo/bar",
        )
        flexmock(self.ga).should_receive("create_gitlab_merge_request").with_args(
            title="[betka-master-sync]", desc_msg=pr_msg, branch=branch_name, origin_branch="",
        ).and_return(mr)
        betka_schema = self.ga.file_merge_request(
            pr_msg=pr_msg, upstream_hash=upstream_hash, branch=branch_name, origin_branch="", mr=None
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
            title="[betka-master-sync]", desc_msg=pr_msg, branch=branch_name, origin_branch="",
        ).and_return(mr_id)
        betka_schema = self.ga.file_merge_request(
            pr_msg=pr_msg, upstream_hash=upstream_hash, branch=branch_name, origin_branch="", mr=mr_id
        )
        assert not betka_schema

    def test_file_merge_request_update(self):
        pr_msg = "Update"
        branch_name = "f35"
        mr_id = 13
        upstream_hash = "10938482734aeb"
        mr = ProjectMR(
            mr_id, "[betka-master-sync]", pr_msg, "rhel-8.6.0", "phracek",
            PROJECT_ID_FORK, PROJECT_ID, "https://gitlab/foo/bar",
        )
        flexmock(self.ga).should_receive("create_gitlab_merge_request").with_args(
            title="[betka-master-sync]", desc_msg=pr_msg, branch=branch_name, origin_branch="",
        ).and_return(mr)
        betka_schema = self.ga.file_merge_request(
            pr_msg=pr_msg, upstream_hash=upstream_hash, branch=branch_name, origin_branch="", mr=mr
        )
        assert betka_schema
        assert betka_schema["commit"] == upstream_hash
        assert betka_schema["merge_request_dict"]
        assert betka_schema["mr_number"] is mr_id
        assert betka_schema["namespace_containers"] == "container"
        assert (
            betka_schema["downstream_repo"]
            == "https://github.com/sclorg/s2i-base-container"
        )
        assert betka_schema["status"] == "updated"

    def test_gitlab_fork_valid(self):
        flexmock(self.ga).should_receive("get_project_forks").and_return(
            [gitlab_fork_exists()]
        )
        flexmock(self.ga).should_receive("load_forked_project").once()
        self.ga.image_config["gitlab_url"] = PROJECT_ID
        self.ga.betka_config["gitlab_user"] = "foo_user"
        fork_exist = self.ga.get_gitlab_fork()
        assert fork_exist

    def test_gitlab_fork_wrong_project_id(self):
        flexmock(self.ga).should_receive("get_project_forks").and_return(
            [gitlab_another_fork()]
        )
        self.ga.project_id = 12345
        fork_exist = self.ga.get_gitlab_fork()
        assert fork_exist is None

    def test_gitlab_fork_wrong_username(self):
        flexmock(self.ga).should_receive("get_project_forks").and_return(
            [gitlab_another_fork()]
        )
        self.ga.betka_config["gitlab_user"] = "wrong_username"
        fork_exist = self.ga.get_gitlab_fork()
        assert not fork_exist

    def test_gitlab_fork_is_missing_creation_failed(self):
        flexmock(self.ga).should_receive("get_project_forks").and_return([])
        flexmock(self.ga).should_receive("fork_project").and_return([])
        fork_exist = self.ga.check_and_create_fork()
        assert not fork_exist

    def test_gitlab_fork_do_not_exists_fork_success(self):
        flexmock(self.ga).should_receive("get_project_forks").and_return([])
        flexmock(self.ga).should_receive("fork_project").and_return(
            gitlab_fork_exists()
        )
        fork_exist = self.ga.check_and_create_fork()
        assert fork_exist
        assert fork_exist.ssh_url_to_repo == "git@gitlab.com:foo/bar.git"
        assert fork_exist.forked_from_id == PROJECT_ID
        assert (
            fork_exist.forked_ssh_url_to_repo
            == "git@gitlab.com:redhat/some/foor/bar.git"
        )

    def test_fork_do_not_exists_fork_failed(self):
        flexmock(self.ga).should_receive("get_project_forks").and_return([])
        flexmock(self.ga).should_receive("fork_project").and_return([])
        assert not self.ga.check_and_create_fork()
