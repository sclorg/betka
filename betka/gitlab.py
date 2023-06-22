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
from typing import Dict, List, Any

from betka.git import Git
from betka.emails import BetkaEmails
from betka.config import fetch_config
from betka.named_tuples import (
    ProjectMRs,
    ProjectBranches,
    ProjectForks,
    CurrentUser,
    ProjectMR,
    ProjectCreateFork,
    ForkProtectedBranches,
    ProjectInfo,
)
from betka.utils import nested_get
from betka.exception import BetkaException

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
        project_id_fork: int = 0,
        fork: bool = False,
    ) -> Any:
        logger.debug(f"get project_id for component: {component}")
        if fork:
            return self.projects.get(project_id_fork)
        else:
            return self.projects.get(image_config["project_id"])


class GitLabAPI(object):
    def __init__(self, betka_config: Dict, config_json: Dict):
        self.betka_config = betka_config
        self.config_json = config_json
        self.gitlab_api_url: str = f"{self.config_json['gitlab_api_url']}"
        self.git = Git()
        self.clone_url: str = ""
        self.upstream_clone_url: str = ""
        self.image: str = ""
        self._gitlab_api = None
        self.gitlab_user = ""
        self.image_config: dict = {}
        self.target_project: Any = None
        self.source_project: Any = None
        self.fork_id = 0
        self.current_user: CurrentUser = None

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
                ssl_verify=True,
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
            self.target_project = self.gitlab_api.projects.get(
                self.image_config["project_id"]
            )

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

    def get_project_forks(self) -> List[ProjectForks]:
        logger.debug(f"Get forks for project {self.image}")
        return [
            ProjectForks(
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
        logger.debug(f"Get branches for project {self.image}")
        return [
            ProjectBranches(x.name, x.web_url, x.protected)
            for x in self.target_project.branches.list()
        ]

    def get_project_mergerequests(self) -> List[ProjectMRs]:
        logger.debug(f"Get mergerequests for project {self.image}")
        project_mr = self.target_project.mergerequests.list(state="opened")
        return [
            ProjectMRs(
                x.iid, x.project_id, x.target_branch, x.title, x.author["username"]
            )
            for x in project_mr
        ]

    def get_project(self, name, group_id):
        """
        Return a Gitlab Project object for the given project name and group id.
        """
        group = self.gitlab_api.groups.get(group_id)
        projects = group.projects.list()  # search=name)
        for project in projects:
            print(project)
            print(self.gitlab_api.projects.get(project.id))

            # if project.name == name:
            #     # return the Project object, not GroupProject
            #     print(self.gitlab_api.projects.get(project.id))
            #     return self.gitlab_api.projects.get(project.id)
        return None

    def create_project_fork(self) -> ProjectCreateFork:
        logger.debug(f"Create fork for project {self.image_config['project_id']}")
        print(
            f"Create fork for project {self.image_config['project_id']} as {self.current_user.username}/{self.image}"
        )
        assert self.target_project
        fork_data = {
            "namespace_path": f"{self.current_user.username}",
            "path": self.image,
        }
        print(fork_data)
        project_mr = self.target_project.forks.create(fork_data)
        print(project_mr)
        return ProjectCreateFork(
            project_mr.id,
            project_mr.name,
            project_mr.ssh_url_to_repo,
            project_mr.web_url,
            project_mr.forked_from_project["id"],
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

    def fork_project(self) -> bool:
        project_id = self.image_config["project_id"]
        logger.debug(f"Create fork for project {project_id}")
        fork: ProjectCreateFork
        try:
            fork = self.create_project_fork()
            logger.debug(f"Fork result {fork}")
        except gitlab.exceptions.GitlabCreateError as gce:
            print(gce)
            if gce.response_code == 409:
                if (
                    "namespace" in gce.error_message
                    and nested_get(gce.error_message, "namespace")[0] == "is not valid"
                ):
                    return False
                logger.debug(
                    f"Fork for project {project_id} already"
                    f"exists with id {self.fork_id}"
                )
                return True
            logger.error(f"{gce.error_message} and {gce.response_code}")
            return False
        print(f"{fork.forked_from_project_id} and {self.image_config['project_id']}")
        if fork.forked_from_project_id != self.image_config["project_id"]:
            logger.debug("Fork project_id is different")
            return False

        self.fork_id = fork.id
        try:
            print("self.load_forked_project()")
            self.load_forked_project()
        except BetkaException:
            logger.error(f"Betka detected problem with fork for project {project_id}.")
            return False
        protected_branches = self.get_protected_branches()
        print(protected_branches)
        logger.debug(f"Protected branches are {protected_branches}")
        for brn in protected_branches:
            self.source_project.protectedbranches.delete(brn.name)
        return True

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
            mr = self.source_project.mergerequests.create(data)
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
            if gce.response_code == 409:
                logger.error("Another PR already exists")
            return None

    def file_merge_request(
        self,
        pr_msg: str,
        upstream_hash: str,
        branch: str,
        mr_id: int,
    ) -> Dict:
        """
        Files a Pull Request with specific messages and text.
        :param pr_msg: description message used in pull request
        :param upstream_hash: commit hash for
        :param branch: specify downstream branch for file a Pull Request
        :param mr_id: PR number if we sync Pull Requests
        :return: schema for sending email
        """
        title = self.betka_config["downstream_master_msg"]
        betka_schema: Dict = {}
        text_mr = "master"
        logger.info(
            f"Downstream {text_mr} sync merge request for image {self.image} is {mr_id}"
        )
        if not mr_id:
            # In case downstream Pull Request does not exist, file a new one
            logger.debug(f"Upstream {text_mr} to downstream PR not found.")

            mr: ProjectMR = self.create_gitlab_merge_request(
                title=title, desc_msg=pr_msg, branch=branch
            )
            print(mr)
            if mr is None:
                logger.error("Merge request was not created. See logs.")
                BetkaEmails.send_email(
                    text=f"Merge request for {self.image} to branch failed. see logs for reason.",
                    receivers=["phracek@redhat.com"],
                    subject="[betka-run] Merge request creation failed.",
                )
                return betka_schema
            betka_schema["status"] = "created"
            mr_id = int(mr.iid)
            betka_schema["merge_request_dict"] = mr

        else:
            # Update pull request against the latest upstream master branch
            logger.debug(f"Sync from upstream to downstream PR={mr_id} found.")
            betka_schema["status"] = "updated"

        upstream_url = ""
        image_config = nested_get(self.betka_config, "dist_git_repos", self.image)
        if image_config:
            upstream_url = image_config["url"]

        betka_schema["downstream_repo"] = upstream_url
        betka_schema["gitlab"] = self.config_json["gitlab_host_url"]
        betka_schema["commit"] = upstream_hash
        betka_schema["mr_number"] = mr_id
        betka_schema["namespace_containers"] = self.config_json["namespace_containers"]
        return betka_schema

    def init_projects(self) -> bool:
        self.target_project = self.gitlab_api.get_component_project_from_config(
            image_config=self.image_config, component=self.image
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
        self, title: str, desc_msg: str, branch: str
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
            "target_project_id": self.image_config["project_id"],
        }
        return self.create_project_mergerequest(data)

    def check_gitlab_merge_requests(self, branch: str):
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
            project_id = self.image_config["project_id"]
            if int(mr.project_id) != int(project_id):
                logger.debug(
                    f"check_gitlab_merge_requests: "
                    f"This Merge Request is not valid for project {int(project_id)}"
                )
                print("Project_id different")
                continue
            if mr.target_branch != branch:
                logger.debug(
                    "check_gitlab_merge_requests: Target branch does not equal."
                )
                print("target_branch is different")
                continue
            if not mr.title.startswith(title):
                logger.debug(
                    "check_gitlab_merge_requests: This Merge request was not filed by betka"
                )
                print(f"Title is {mr.title}")
                continue
            logger.debug(
                f"check_gitlab_merge_requests: Downstream pull request {title} found {mr.iid}"
            )
            return mr.iid
        return None

    def get_branches(self) -> List[str]:
        """
        Gets the valid branches which contains `bot-cfg.yml` file.
        :param project_id: str Specify project id for getting list of branches
        :return: list of valid branches
        """
        branches_list = []
        resp = self.get_project_branches()
        for brn in resp:
            branches_list.append(brn.name)
        return branches_list

    def get_clone_url(self) -> str:
        return self.clone_url

    def get_upstream_clone_url(self) -> str:
        return self.upstream_clone_url

    def get_gitlab_fork(self) -> bool:
        """
        Checks if the fork already exists in the internal Pagure instance
        otherwise it will create it.
        :return: True if fork exists
                 False if fork not exists
        """
        fork_found: bool = False
        forks = self.get_project_forks()
        for f in forks:
            if f.forked_id == nested_get(self.image_config, "project_id_fork"):
                self.clone_url = f.ssh_url_to_repo
                self.upstream_clone_url = f.forked_ssh_url_to_repo
                fork_found = True
        return fork_found

    # URL address is: https://gitlab.com/redhat/rhel/containers/nodejs-10/-/raw/rhel-8.6.0/bot-cfg.yml
    def cfg_url(self, branch, file="bot-cfg.yml"):
        return (
            f"{self.config_json['gitlab_host_url']}/"
            f"{self.config_json['gitlab_namespace']}/"
            f"{self.image}/-/raw/{branch}/{file}"
        )

    def get_bot_cfg_yaml(self, branch: str) -> Dict:
        """
        :return: bot-cfg.yml config
        """
        source_url = self.cfg_url(
            branch=branch,
        )
        return fetch_config("upstream-to-downstream", source_url)
