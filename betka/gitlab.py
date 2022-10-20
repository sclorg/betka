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
import requests
import time

from typing import Dict, List

from betka.git import Git
from betka.config import fetch_config

logger = logging.getLogger(__name__)


class GitLabAPI(object):
    def __init__(self, betka_config: Dict, config_json: Dict):
        self.betka_config = betka_config
        self.config_json = config_json
        self.gitlab_api_url: str = f"{self.config_json['gitlab_api_url']}"
        self.git = Git()
        self.clone_url: str = ""
        self.upstream_clone_url: str = ""
        self.project_id: int = 0
        self.image: str = ""

    def set_variables(self, project_id: int, image: str):
        # TODO use setter method
        self.project_id = project_id
        self.image = image

    def gitlab_post_action(self, url: str, data=None):
        """
        Set authorization for operating with Pull Request
        :param url: URL
        :param data: ?
        :return: response from POST request as json
        """
        logger.debug("gitlab_post_action(url=%s, data=%s)", url, data)
        try:
            r = requests.post(
                url,
                data=data,
                headers={
                    "PRIVATE-TOKEN": f"{self.betka_config['gitlab_api_token'].strip()}"
                },
            )
            r.raise_for_status()
            logger.debug("response: %s", r.json())
            return r.status_code, r.json()

        except requests.exceptions.HTTPError as he:
            logger.exception(he)
            raise

    def gitlab_get_action(self, url: str):
        """
        Set authorization for operating with Pull Request
        :param url: URL
        :param data: ?
        :return: response from POST request as json
        """
        logger.debug("gitlab_post_action(url=%s)", url)
        try:
            r = requests.get(
                url,
                headers={
                    "PRIVATE-TOKEN": f"{self.betka_config['gitlab_api_token'].strip()}"
                },
            )
            r.raise_for_status()
            logger.debug("response: %s", r.json())
            return r.status_code, r.json()

        except requests.exceptions.HTTPError as he:
            logger.exception(he)
            raise

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
            mr_id = self.create_gitlab_merge_request(
                title=title, desc_msg=pr_msg, branch=branch
            )
            if mr_id is None:
                return betka_schema
            betka_schema["status"] = "created"

        else:
            # Update pull request against the latest upstream master branch
            logger.debug(f"Sync from upstream to downstream PR={mr_id} found.")
            betka_schema["status"] = "updated"

        upstream_url = ""
        for key in self.betka_config["dist_git_repos"]:
            if self.image not in key:
                continue
            values = self.betka_config["dist_git_repos"][key]
            upstream_url = values["url"]

        betka_schema["downstream_repo"] = upstream_url
        betka_schema["gitlab"] = self.config_json["gitlab_host_url"]
        betka_schema["commit"] = upstream_hash
        betka_schema["mr_number"] = mr_id
        betka_schema["namespace_containers"] = self.config_json["namespace_containers"]
        return betka_schema

    def create_gitlab_merge_request(
        self, title: str, desc_msg: str, branch: str
    ) -> int:
        """
        Creates the pull request for specific image
        :param title: ?
        :param desc_msg: ?
        :param branch: ?
        :return:
        """
        logger.debug(f"create_gitlab_merge_pull_request(): {branch}")
        url_address = self.get_url("gitlab_create_merge_request")
        data = {
            "title": title,
            "target_branch": branch,
            "source_branch": branch,
            "description": desc_msg,
            "allow_collaboration": True,
        }

        ret_json = self.gitlab_post_action(url_address, data=data)
        try:
            return ret_json.get("id")
        except AttributeError:
            return None

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
        url_address = self.get_url(url_key="gitlab_list_mr")
        logger.debug(url_address)
        _, resp = self.gitlab_get_action(url=url_address)
        for mr in resp:
            if "project_id" not in mr and mr["project_id"] != self.project_id:
                logger.debug(
                    f"check_gitlab_merge_requests: "
                    f"This Merge Request is not valid for project {self.project_id}"
                )
                continue
            if mr["target_branch"] != branch:
                logger.debug(
                    "check_gitlab_merge_requests: Target branch does not equal."
                )
                continue
            if not mr["title"].startswith(title):
                logger.debug(
                    "check_gitlab_merge_requests: This Merge request was not filed by betka"
                )
                print(f"Tiel is {mr['title']}")
                continue
            logger.debug(
                f"check_gitlab_merge_requests: Downstream pull request {title} found {mr['iid']}"
            )
            return mr["iid"]
        return None

    def get_url(self, url_key: str) -> str:
        url_address = f"{self.config_json['gitlab_api_url']}{self.config_json[url_key]}"
        url_address = url_address.format(id=self.project_id)
        return url_address

    def get_user_from_token(self):
        url_address = (
            f"{self.config_json['gitlab_api_url']}{self.config_json['gitlab_url_user']}"
        )
        logger.debug(url_address)
        status_code, resp = self.gitlab_get_action(url_address)
        if status_code == 400:
            return None
        if "username" not in resp:
            return None
        return resp["username"]

    def get_branches(self) -> List[str]:
        """
        Gets the valid branches which contains `bot-cfg.yml` file.
        :param project_id: str Specify project id for getting list of branches
        :return: list of valid branches
        """
        branches_list = []
        url_address = self.get_url(url_key="gitlab_branches")
        logger.debug(url_address)
        _, resp = self.gitlab_get_action(url=url_address)
        for brn in resp:
            branches_list.append(brn["name"])
        return branches_list

    def get_fork(self, count: int = 20) -> bool:
        """
        Gets the fork for specific repo
        :param count: How many times we would like to test if fork exist.
                    Sometimes getting fork takes a bit longer.
        :return:
        """
        logger.debug(f"get_fork() for project {self.project_id}")
        url_address = self.get_url(url_key="gitlab_forks")
        for i in range(0, count):
            (status_code, resp) = self.gitlab_get_action(url_address)
            if status_code == 400:
                logger.warning(f"Unauthorized access to url {url_address}")
                return False
            if status_code == 200 and resp:
                for req in resp:
                    if "ssh_url_to_repo" not in req:
                        return False
                    self.clone_url = req["ssh_url_to_repo"]
                    if "forked_from_project" not in req:
                        logger.info(
                            f"Project {self.project_id} is not a fork. Skipping."
                        )
                        return False
                    self.upstream_clone_url = req["forked_from_project"][
                        "ssh_url_to_repo"
                    ]
                    return True
            logger.info(
                "Fork %s is not ready yet. Wait 2 more seconds. " "Status code %s ",
                url_address,
                status_code,
            )
            time.sleep(2)
        logger.info("Betka does not have a fork yet.")
        return False

    def get_clone_url(self) -> str:
        return self.clone_url

    def get_upstream_clone_url(self) -> str:
        return self.upstream_clone_url

    def get_access_request(self):
        url_address = self.get_url("gitlab_access_request")
        (status_code, resp) = self.gitlab_get_action(url_address)

    def get_gitlab_fork(self) -> bool:
        """
        Checks if the fork already exists in the internal Pagure instance
        otherwise it will create it.
        :return: True if fork exists
                 False if fork not exists
        """
        url_address = self.get_url("gitlab_fork_project")
        if not self.get_fork(count=1):
            status_code, resp = self.gitlab_post_action(url_address)
            # If we do not have fork, then it fails
            # Wait 20 seconds before fork is created
            if not self.get_fork():
                logger.info(f"{self.image} does not have a fork yet" f"{self.image}")
                return False
        return True

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
