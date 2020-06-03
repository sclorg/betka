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
from pathlib import Path

from frambo.config import fetch_config
from frambo.pagure import PAGURE_PORT
from frambo.pagure import cfg_url

from betka.git import Git
from betka.constants import DOWNSTREAM_CONFIG_FILE, SYNCHRONIZE_BRANCHES
from betka.urls import (
    NAMESPACE_CONTAINERS,
    PULL_REQUEST_URL,
    PR_API,
    API_URL,
    GET_USER_URL,
    GET_PR_COMMENT,
    GET_ALL_PR,
    PAGURE_HOST,
    PAGURE_HOST_HTTPS,
    PR_FORK,
)


logger = logging.getLogger(__name__)


class PagureAPI(object):
    def __init__(self, config: Dict):
        self.config = config
        self.pagure_api_url: str = f"{PAGURE_HOST_HTTPS}{API_URL}"
        self.git = Git()
        self.clone_url: str = ""

    def set_image(self, image: str):
        # TODO use setter method
        self.image = image

    def set_pagure_user(self, username: str):
        self.username = username

    def get_user_from_token(self):
        """
        Gets the username from token provided by parameter in betka's template.
        :return: username or None
        """
        ret_json = self.pagure_post_action(GET_USER_URL)
        if "username" not in ret_json:
            return None
        return ret_json["username"]

    def pagure_post_action(self, url: str, data=None):
        """
        Set authorization for operating with Pull Request
        :param url: URL
        :param data: ?
        :return: response from POST request as json
        """
        logger.debug("pagure_post_action(url=%s, data=%s)", url, data)
        logger.debug(self.config)
        try:
            r = requests.post(
                url,
                data=data,
                headers={"Authorization": f"token {self.config['pagure_api_token']}"},
            )
            r.raise_for_status()
            logger.debug("response: %s", r.json())
            return r.json()

        except requests.exceptions.HTTPError as he:
            logger.exception(he)
            raise

    def check_downstream_pull_requests(
        self, msg_to_check: str, branch: str, check_user: bool = True
    ):
        """
        Checks if downstream already contains pull request. Check is based in the msg_to_check
        parameter.
        :return:
        """
        url_address = self.pagure_api_url + GET_ALL_PR.format(
            namespace=NAMESPACE_CONTAINERS, repo=self.image
        )
        logger.debug(url_address)
        (status_code, resp) = self.get_status_and_dict_from_request(url=url_address)
        req = resp["requests"]
        user = self.config["pagure_user"]
        for out in req:
            if out["status"] != "Open":
                continue
            if out["title"].startswith(msg_to_check):
                pr_id = out["id"]
                logger.debug(
                    "Downstream pull request for message %r " "and user %r found %r",
                    msg_to_check,
                    user,
                    pr_id,
                )
                # Check if the PR is for correct branch
                if out["branch"] != branch:
                    continue
                if check_user and out["user"]["name"] == user:
                    return pr_id
                else:
                    return pr_id
        return None

    def create_pagure_pull_request(
        self, title: str, desc_msg: str, hashid: str, branch: str
    ):
        """
        Creates the pull request for specific image
        :param title: ?
        :param desc_msg: ?
        :param hashid: ?
        :param branch: ?
        :return:
        """
        logger.debug(f"create_pagure_pull_request(): {branch}")
        url_address = PAGURE_HOST_HTTPS + PR_API
        url_address = url_address.format(
            namespace=NAMESPACE_CONTAINERS, repo=self.image
        )
        logger.debug(url_address)
        # Commit message looks like:
        # <User defined commit Title>\n\n
        # UpstreamCommitID: {hash}\n
        # UpstreamCommitLink: {repo}/commit/{hash}\n
        # UpstreamRepository: {repo}
        data = {
            "title": title,
            "branch_to": branch,
            "branch_from": branch,
            "initial_comment": "TEST BETKA",
            "repo_from": self.image,
            "repo_from_namespace": NAMESPACE_CONTAINERS,
            "repo_from_username": self.username,
        }
        logger.debug(f"url_address: {url_address}, data: {data}")
        ret_json = self.pagure_post_action(url_address, data=data)
        try:
            return ret_json.get("id")
        except AttributeError:
            return None

    def get_pagure_fork(self):
        """
        Checks if the fork already exists in the internal Pagure instance
        otherwise it will create it.
        :return: True if fork exists
                 False if fork not exists
        """
        data = {"namespace": NAMESPACE_CONTAINERS, "repo": self.image}
        if not self.get_fork(count=1):
            self.pagure_post_action(PAGURE_HOST_HTTPS + PR_FORK, data=data)
            # If we do not have fork, then it fails
            # Wait 20 seconds before fork is created
            if not self.get_fork():
                logger.info(
                    f"{self.image} does not have a fork in {NAMESPACE_CONTAINERS}"
                    f" namespace yet"
                )
                return False
        return True

    def get_comment_url(self, internal_repo: str, pr_id: str):
        comment_url = self.pagure_api_url + GET_PR_COMMENT.format(
            namespace=NAMESPACE_CONTAINERS, repo=internal_repo, id=pr_id
        )
        return comment_url

    @property
    def _full_url(self):
        """
        Returns the full URL for the relevant repo image.
        :return: Full URL for image
        """
        pagure_url = "{url}/fork/{user}/{namespace}/{repo}/git/".format(
            url=self.pagure_api_url,
            user=self.config["pagure_user"],
            namespace=NAMESPACE_CONTAINERS,
            repo=self.image,
        )
        return pagure_url

    @property
    def full_downstream_url(self) -> str:
        """
        Returns the full downstream URL for the relevant repo image.
        Example: ssh://git@src.fedoraproject.org/container/s2i-base.git
        :return: Full URL for image
        """
        url = (
            f"ssh://{self.username}@{PAGURE_HOST}:{PAGURE_PORT}"
            if PAGURE_PORT
            else PULL_REQUEST_URL.format(username=self.username)
        )
        return f"{url}/{NAMESPACE_CONTAINERS}/{self.image}.git"

    def get_clone_url(self) -> str:
        return self.clone_url

    def get_status_and_dict_from_request(self, url: str = None, msg: str = ""):
        if not url:
            url = self._full_url
        f = requests.get(url + msg, verify=False)
        return f.status_code, f.json()

    def get_fork(self, count: int = 20) -> bool:
        """
        Gets the fork for specific repo
        :param count: How many times we would like to test if fork exist.
                    Sometimes getting fork takes a bit longer.
        :return:
        """
        logger.debug(f"get_fork(): {self._full_url} ")
        for i in range(0, count):
            (status_code, req) = self.get_status_and_dict_from_request(msg="urls")
            if status_code == 400:
                logger.warning("Unauthorized access to url %s", self._full_url)
                return False
            if status_code == 200 and req:
                logger.debug("response get_fork: %s", req)
                self.clone_url = req["urls"]["ssh"]
                self.clone_url = self.clone_url.format(username=self.username)
                return True
            logger.info(
                "Fork %s is not ready yet. Wait 2 more seconds. " "Status code %s ",
                self._full_url,
                status_code,
            )
            time.sleep(2)
        logger.info("Betka does not have a fork yet.")
        return False

    def check_config_in_branch(self, downstream_dir: Path, branch: str) -> bool:
        """
        Checks if the downstream branch contains 'bot-cfg.yml' file
        :param downstream_dir: Path to downstream directory where betka expects `bot-cfg.yml` file
        :param branch: Branch which betka checks
        :return: True if config file exists
                 False is config file does not exist
        """
        # Switch to proper branch
        self.git.call_git_cmd(f"checkout {branch}", msg="Change downstream branch")
        if (downstream_dir / DOWNSTREAM_CONFIG_FILE).exists():
            logger.info(
                "Configuration file %r exists in branch.", DOWNSTREAM_CONFIG_FILE
            )
            return True
        else:
            logger.info(
                "Configuration file %r does not exist in branch.",
                DOWNSTREAM_CONFIG_FILE,
            )
            return False

    def branches_to_synchronize(self, all_branches: List[str]) -> List[str]:
        """
        Checks if branch mentioned in betka configuration file
        is mentioned in valid_branches
        :return: list of valid branches to sync
        """
        synchronize_branches = tuple(self.config.get(SYNCHRONIZE_BRANCHES, []))
        return [b for b in all_branches if b.startswith(synchronize_branches)]

    def get_valid_branches(self, downstream_dir: Path) -> List[str]:
        """
        Gets the valid branches which contains `bot-cfg.yml` file.
        :param downstream_dir:
        :return: list of valid branches
        """
        branch_list = self._get_branches()
        valid_branches = []
        for brn in branch_list:
            logger.debug("Checking 'bot-cfg.yml' in git directory in branch %r", brn)
            if self.check_config_in_branch(downstream_dir, brn):
                valid_branches.append(brn)
        if not valid_branches:
            logger.info("%r does not contain any branch for syncing.", self.image)
            return []
        return self.branches_to_synchronize(valid_branches)

    def _get_branches(self) -> List[str]:
        """
        Gets all branches with bot-cfg.yml file
        """
        for i in range(0, 20):
            (status_code, req) = self.get_status_and_dict_from_request(msg="branches")
            if status_code == 200:
                logger.debug(req)
                # Remove master branch and private branches
                return req["branches"]
            logger.info(
                f"Status code for branches %s is %s", self._full_url, status_code
            )
            time.sleep(2)

        logger.info("Betka does not have a branch yet.")
        return []

    def file_pull_request(
        self,
        commit_msg,
        msg_to_check,
        description_msg,
        upstream_hash,
        branch,
        pr_id,
        pr=False,
        pr_num=None,
    ) -> Dict:
        """
        Files a Pull Request with specific messages and text.
        :param commit_msg: message used to file a pull request as a title
        :param msg_to_check: message used to check is pull request already exist or no
        :param description_msg: description message used in pull request
        :param upstream_hash: commit hash for
        :param branch: specify downstream branch for file a Pull Request
        :param pr: flag if we file a upstream master Pull Request or upstream Pull Request itself
        :param pr_num: pull request number
        :return: schema for sending email
        """
        betka_schema: Dict = {}
        text_pr = "PR" if pr else "master"
        logger.info(
            f"Downstream {text_pr} sync pull request for image {self.image} is {pr_id}"
        )
        if not pr_id:
            # In case downstream Pull Request does not exist, file a new one
            logger.debug(f"Upstream {text_pr} to downstream PR not found.")
            pr_id = self.create_pagure_pull_request(
                msg_to_check, description_msg, upstream_hash, branch
            )
            if pr_id is None:
                return betka_schema
            betka_schema["status"] = "created"

        else:
            # Update pull request against the latest upstream master branch
            logger.debug(f"Sync from upstream to downstream PR={pr_id} found.")
            betka_schema["status"] = "updated"
        betka_schema["downstream_repo"] = "".join(
            [x for x in self.config["dist_git_repos"] if self.image in x]
        )

        betka_schema["pagure"] = PAGURE_HOST
        betka_schema["commit"] = upstream_hash
        betka_schema["pr_number"] = pr_num if pr else pr_id
        betka_schema["namespace"] = NAMESPACE_CONTAINERS
        return betka_schema

    def get_bot_cfg_yaml(self, branch: str) -> Dict:
        """
        :return: bot-cfg.yml config
        """
        source_url = cfg_url(repo=f"{NAMESPACE_CONTAINERS}/{self.image}", branch=branch)
        return fetch_config("upstream-to-downstream", source_url)
