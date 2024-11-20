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


import logging
import gitlab
import time
import requests

from requests.exceptions import HTTPError
from typing import Dict, List, Any

from betka.git import Git
from betka.emails import BetkaEmails
from betka.config import fetch_config
from betka.named_tuples import (
    ProjectBranches,
    ProjectFork,
    CurrentUser,
    ProjectMR,
    ForkProtectedBranches,
    ProjectInfo,
)
from betka.utils import nested_get
from betka.exception import BetkaException

requests.packages.urllib3.disable_warnings()


logger = logging.getLogger(__name__)


class GitLab(gitlab.Gitlab):
    """
    Extended GitLab API wrapper.

    This class extends the GitLab API wrapper to add a method for getting the
    project object for a given component.
    python-gitlab docs are available here https://python-gitlab.readthedocs.io/en/stable/index.html
    """

    def get_component_project_from_config(
        self,
        image_config: Dict,
        component: str,
        project_id: int = 0,
        project_id_fork: int = 0,
        fork: bool = False,
    ) -> Any:
        logger.debug(f"get project_id for component: {component}")
        if fork:
            return self.projects.get(project_id_fork)
        else:
            return self.projects.get(project_id)


class GitLabAPI(object):
    def __init__(self, betka_config: Dict, config_json: Dict):
        self.betka_config = betka_config
        self.config_json = config_json
        self.gitlab_api_url: str = f"{self.config_json['gitlab_api_url']}"
        self.git = Git()
        self.ssh_url_to_repo: str = ""
        self.forked_ssh_url_to_repo: str = ""
        self.image: str = ""
        self._gitlab_api = None
        self.gitlab_user = ""
        self.image_config: dict = {}
        self.target_project: Any = None
        self.source_project: Any = None
        self.fork_id = 0
        self.current_user: CurrentUser = None
        self.project_id = None

    def __str__(self) -> str:
        return f"betka_config:{self.betka_config}\n" f"config_json:{self.config_json}"

    def set_variables(self, image: str):
        # TODO use setter method
        self.image = image
        self.image_config = nested_get(self.betka_config, "dist_git_repos", self.image)

    @property
    def gitlab_api(self):
        if not self._gitlab_api:
            self._gitlab_api = GitLab(
                "https://gitlab.com",
                private_token=self.betka_config["gitlab_api_token"].strip(),
                ssl_verify=False,
            )
        return self._gitlab_api

    def check_authentication(self):
        try:
            self.gitlab_api.auth()
            current_user = self.gitlab_api.user
            self.current_user = CurrentUser(current_user.id, current_user.username)
            return self.current_user
        except gitlab.exceptions.GitlabAuthenticationError as gae:
            logger.error(f"Authentication failed with reason {gae}.")
            return None

    def load_project(self, fork=False):
        if fork:
            self.source_project = self.gitlab_api.projects.get(self.fork_id)
        else:
            self.target_project = self.gitlab_api.projects.get(self.project_id)

    def check_username(self) -> bool:
        user_name = self.check_authentication()
        if not user_name:
            BetkaEmails.send_email(
                text="GitLab authentication failed. GITLAB_API_TOKEN is wrong.",
                receivers=["phracek@redhat.com"],
                subject="[betka-prepare] Gitlab check authentication failed.",
            )
            return False
        if user_name.username != self.betka_config["gitlab_user"]:
            BetkaEmails.send_email(
                text="GitLab authentication failed. Username is different",
                receivers=["phracek@redhat.com"],
                subject="[betka-prepare] Gitlab check authentication failed.",
            )
            return False
        return True

    def get_project_forks(self) -> List[ProjectFork]:
        logger.debug(f"Get forks for project {self.image}")
        return [
            ProjectFork(
                x.id,
                x.name,
                x.ssh_url_to_repo,
                x.owner["username"],
                x.forked_from_project["id"],
                x.forked_from_project["ssh_url_to_repo"],
            )
            for x in self.target_project.forks.list()
        ]

    def get_project_branches(self) -> List[ProjectBranches]:
        logger.debug(f"Get branches for project {self.image}: {self.target_project.branches.list()}")
        return [
            ProjectBranches(x.name, x.web_url, x.protected)
            for x in self.target_project.branches.list()
        ]

    def get_target_protected_branches(self) -> List[ForkProtectedBranches]:
        logger.debug(f"Get protected branches for project {self.image}: {self.target_project.protectedbranches.list()}")
        protected_branches = self.target_project.protectedbranches.list()
        return [ForkProtectedBranches(x.name) for x in protected_branches]

    def get_project_mergerequests(self) -> List[ProjectMR]:
        logger.debug(f"Get mergerequests for project {self.image}")
        project_mr = self.target_project.mergerequests.list(state="opened")
        return [
             ProjectMR(
                x.iid,
                x.title,
                x.description,
                x.target_branch,
                x.author["username"],
                x.source_project_id,
                x.target_project_id,
                x.web_url,
            )
            for x in project_mr
        ]

    def create_project_fork(self) -> ProjectFork:
        logger.debug(f"Create fork for project {self.project_id}")
        assert self.target_project
        fork_data = {
            "namespace_path": f"{self.current_user.username}",
            "path": self.image,
        }
        project_mr = self.target_project.forks.create(fork_data)
        return ProjectFork(
            project_mr.id,
            project_mr.name,
            project_mr.ssh_url_to_repo,
            project_mr.owner["username"],
            project_mr.forked_from_project["id"],
            project_mr.forked_from_project["ssh_url_to_repo"],
        )

    def load_forked_project(self):
        for cnt in range(0, 20):
            try:
                self.load_project(fork=True)
                break
            except gitlab.exceptions.GitlabGetError as gge:
                logger.debug(gge.response_code, gge.error_message)
                if gge.response_code == 404:
                    logger.debug("Let's wait couple seconds, till fork is not created.")
                else:
                    raise BetkaException(
                        "Fork was created but does not exist after 20 seconds"
                    )
            # Let's wait 2 more seconds
            time.sleep(2)

    def get_protected_branches(self) -> List[ForkProtectedBranches]:
        logger.debug(f"Get protected branches for fork {self.fork_id}")
        protected_branches = self.source_project.protectedbranches.list()
        return [ForkProtectedBranches(x.name) for x in protected_branches]

    def fork_project(self) -> Any:
        logger.debug(f"Create fork for project {self.project_id}")
        fork: ProjectFork
        try:
            fork = self.create_project_fork()
            logger.debug(f"Fork result {fork}")
        except gitlab.exceptions.GitlabCreateError as gce:
            logger.debug(gce)
            if gce.response_code == 409:
                if (
                    "namespace" in gce.error_message
                    and nested_get(gce.error_message, "namespace")[0] == "is not valid"
                ):
                    return None
                logger.debug(
                    f"Fork for project {self.project_id} already"
                    f"exists with id {self.fork_id}"
                )
                return fork
            logger.error(f"{gce.error_message} and {gce.response_code}")
            return None
        logger.debug(f"{fork.forked_from_id} and {self.project_id}")
        if fork.forked_from_id != self.project_id:
            logger.debug("Fork project_id is different")
            return None

        self.fork_id = fork.id
        self.ssh_url_to_repo = fork.ssh_url_to_repo
        self.forked_ssh_url_to_repo = fork.forked_ssh_url_to_repo
        try:
            self.load_forked_project()
        except BetkaException:
            logger.error(f"Betka detected problem with fork for project {self.project_id}.")
            return None
        protected_branches = self.get_protected_branches()
        logger.debug(f"Protected branches are {protected_branches}")
        for brn in protected_branches:
            self.source_project.protectedbranches.delete(brn.name)
        return fork

    def get_project_info(self) -> ProjectInfo:
        logger.debug(
            f"Get information for project {self.target_project.name} with id {self.target_project.id}"
        )
        return ProjectInfo(
            self.target_project.id,
            self.target_project.name,
            self.target_project.ssh_url_to_repo,
            self.target_project.web_url,
        )

    def create_project_mergerequest(self, data) -> ProjectMR:
        logger.debug(f"Create mergerequest for project {self.image} with data {data}")
        try:
            if self.is_fork_enabled():
                mr = self.source_project.mergerequests.create(data)
            else:
                mr = self.target_project.mergerequests.create(data)
            return ProjectMR(
                mr.iid,
                mr.title,
                mr.description,
                mr.target_branch,
                mr.author["username"],
                mr.source_project_id,
                mr.target_project_id,
                mr.web_url,
            )
        except gitlab.exceptions.GitlabCreateError as gce:
            logger.error(f"{gce.error_message} and {gce.response_code}")
            BetkaEmails.send_email(
                text=f"GitLab create project merge request for project {self.image} with data {data}",
                receivers=["phracek@redhat.com"],
                subject="[betka-create-mergerequest] Gitlab Another MR mergerequest already exists.",
            )
            if gce.response_code == 409:
                logger.error("Another MR already exists")
            return None

    def is_fork_enabled(self):
        value = self.betka_config["use_gitlab_forks"].lower()
        if value in ["true", "yes"]:
            return True
        return False

    def file_merge_request(
        self,
        pr_msg: str,
        upstream_hash: str,
        branch: str,
        origin_branch: str,
        mr: Any,
    ) -> Dict:
        """
        Files a Pull Request with specific messages and text.
        :param pr_msg: description message used in pull request
        :param upstream_hash: commit hash for
        :param branch: specify downstream branch for file a Pull Request
        :param origin_branch: specify origin_branch to which file a Pull Request
        :param mr: named touple ProjectMR
        :return: schema for sending email
        """
        title = self.betka_config["downstream_master_msg"]
        betka_schema: Dict = {}
        text_mr = "master"
        if not mr:
            # In case downstream Pull Request does not exist, file a new one
            logger.debug(f"Upstream {text_mr} to downstream PR not found.")

            mr: ProjectMR = self.create_gitlab_merge_request(
                title=title, desc_msg=pr_msg, branch=branch, origin_branch=origin_branch
            )
            logger.debug(f"MergeRequest is: {mr}")
            if mr is None:
                logger.error("Merge request was not created. See logs.")
                BetkaEmails.send_email(
                    text=f"Merge request for {self.image} to branch {branch} failed. See logs on OpenShift for reason.",
                    receivers=["phracek@redhat.com"],
                    subject="[betka-run] Merge request creation failed.",
                )
                return betka_schema
            betka_schema["status"] = "created"
            mr_id = int(mr.iid)
            betka_schema["merge_request_dict"] = mr
            betka_schema["image"] = self.image

        else:
            logger.info(
                f"Downstream {text_mr} sync merge request for image {self.image} is {mr.iid}"
            )
            # Update pull request against the latest upstream master branch
            logger.debug(f"Sync from upstream to downstream PR={mr.iid} found.")
            betka_schema["status"] = "updated"
            betka_schema["image"] = self.image
            betka_schema["merge_request_dict"] = mr

        upstream_url = ""
        image_config = nested_get(self.betka_config, "dist_git_repos", self.image)
        if image_config:
            upstream_url = image_config["url"]

        betka_schema["downstream_repo"] = upstream_url
        betka_schema["gitlab"] = self.config_json["gitlab_host_url"]
        betka_schema["commit"] = upstream_hash
        betka_schema["mr_number"] = mr.iid
        betka_schema["namespace_containers"] = self.config_json["gitlab_namespace"]
        return betka_schema

    def init_projects(self) -> bool:
        self.target_project = self.gitlab_api.get_component_project_from_config(
            image_config=self.image_config, component=self.image, project_id=self.project_id
        )
        if self.fork_id != 0:
            self.source_project = self.gitlab_api.get_component_project_from_config(
                image_config=self.image_config,
                component=self.image,
                project_id_fork=self.fork_id,
                fork=True,
            )
        return True

    def create_gitlab_merge_request(
        self, title: str, desc_msg: str, branch: str, origin_branch: str,
    ) -> ProjectMR:
        """
        Creates the pull request for specific image
        :param title: ?
        :param desc_msg: ?
        :param branch: ?
        :return:
        """
        logger.debug(f"create_gitlab_merge_pull_request(): {branch}")
        data = {
            "title": title,
            "target_branch": branch,
            "source_branch": branch,
            "description": desc_msg,
            "target_project_id": self.project_id,
        }
        if not self.betka_config["use_gitlab_forks"]:
            data["target_branch"] = origin_branch
        return self.create_project_mergerequest(data)

    def check_gitlab_merge_requests(self, branch: str, target_branch: str):
        """
        Checks if downstream already contains pull request. Check is based in the msg_to_check
        parameter.
        :param: branch: str Specify branch for specific project
                project_id: str Specify project id for getting list of MRs
        :return: None if component does not contain any valid MR
                 id: if component contains valid MR
        """
        # Function checks if downstream contains pull request or not based on the title message
        title = self.betka_config["downstream_master_msg"]
        list_mr = self.get_project_mergerequests()
        for mr in list_mr:
            if int(mr.target_project_id) != int(self.project_id):
                logger.debug(
                    f"check_gitlab_merge_requests: "
                    f"This Merge Request is not valid for project {int(self.project_id)}"
                )
                logger.debug("Project_id different")
                continue
            if mr.target_branch != target_branch:
                logger.debug(
                    "check_gitlab_merge_requests: Target branch does not equal."
                )
                logger.debug("target_branch is different")
                continue
            if not mr.title.startswith(title):
                logger.debug(
                    "check_gitlab_merge_requests: This Merge request was not filed by betka"
                )
                logger.debug(f"Title is {mr.title}")
                continue
            logger.debug(
                f"check_gitlab_merge_requests: Downstream pull request {title} found {mr.iid}"
            )
            return ProjectMR(
                iid=mr.iid, title=mr.title, description="", target_branch=mr.target_branch, author=mr.author,
                source_project_id=None, target_project_id=int(mr.target_project_id), web_url=""
            )
        return None

    def get_branches(self) -> List[str]:
        """
        Gets the valid branches which contains `bot-cfg.yml` file.
        :param project_id: str Specify project id for getting list of branches
        :return: list of valid branches
        """
        branches_list = []
        resp = self.get_project_branches()
        resp_protected = self.get_target_protected_branches()
        for brn in resp:
            branches_list.append(brn.name)
        for protected in resp_protected:
            branches_list.append(protected.name)
        logger.debug(f"get_branches: {branches_list}")
        return branches_list

    def get_ssh_url_to_repo(self) -> str:
        return self.ssh_url_to_repo

    def get_forked_ssh_url_to_repo(self) -> str:
        return self.forked_ssh_url_to_repo

    def get_gitlab_fork(self) -> Any:
        """
        Checks if the fork already exists in the internal GitLab instance
        otherwise it will create it.
        :return: True if fork exists
                 False if fork not exists
        """
        project_fork: ProjectFork
        forks = self.get_project_forks()
        for fork in forks:
            if fork.forked_from_id != self.project_id:
                continue
            if fork.username != self.betka_config["gitlab_user"]:
                continue
            self.ssh_url_to_repo = fork.ssh_url_to_repo
            self.forked_ssh_url_to_repo = fork.forked_ssh_url_to_repo
            logger.debug(f"Project fork found: {fork}")
            self.fork_id = fork.id
            self.load_forked_project()
            return fork
        return None

    # URL address is: https://gitlab.com/redhat/rhel/containers/nodejs-10/-/raw/rhel-8.6.0/bot-cfg.yml
    def cfg_url(self, branch, file="bot-cfg.yml"):
        return (
            f"{self.config_json['dist_git_url']}/"
            f"{self.image}/plain/{file}?h={branch}"
        )

    def get_bot_cfg_yaml(self, branch: str) -> Dict:
        """
        :return: bot-cfg.yml config
        """
        source_url = self.cfg_url(
            branch=branch,
        )
        return fetch_config(source_url)

    def check_and_create_fork(self):
        project_fork: ProjectFork = self.get_gitlab_fork()
        if not project_fork:
            project_fork: ProjectFork = self.fork_project()
            if not project_fork:
                return None
        return project_fork

    def get_project_id_from_url(self):
        url = "https://gitlab.com/api/v4/projects"
        headers = {
            "Content-Type": "application/json",
            "PRIVATE-TOKEN": self.betka_config["gitlab_api_token"].strip()
        }
        url_namespace = f"redhat/rhel/containers/{self.image}"
        url = f"{url}/{url_namespace.replace('/', '%2F')}"
        logger.debug(f"Get project_id from {url}")
        ret = requests.get(url=f"{url}", headers=headers, verify=False)
        ret.raise_for_status()
        if ret.status_code != 200:
            logger.error(f"Getting project_id failed for reason {ret.reason} {ret.json()} ")
            raise HTTPError
        self.project_id = ret.json()["id"]
        logger.debug(f"Project id returned from {url} is {self.project_id}")
        return self.project_id
