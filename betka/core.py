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

import shutil
import subprocess
import os
import yaml
import time
import traceback
import jsonschema

from os import getenv
from datetime import datetime
from requests import get
from tempfile import TemporaryDirectory
from pprint import pformat
from pathlib import Path
from typing import Dict, List

from frambo.bot import Bot
from frambo.emails import send_email
from frambo.pagure import PAGURE_PORT
from frambo.utils import text_from_template

from betka.git import Git
from betka.github import GitHubAPI
from betka.utils import copy_upstream2downstream, list_dir_content
from betka.pagure import PagureAPI
from betka.constants import (
    GENERATOR_DIR,
    COMMIT_MASTER_MSG,
    COMMIT_PR_MSG,
    NAME,
    TEMPLATES,
    SYNC_INTERVAL,
)
from betka.utils import load_config_json
from betka.umb import UMBSender


class Betka(Bot):

    cfg_key = "upstream-to-downstream"

    def __init__(self, task_name=None):
        super().__init__(task_name=task_name)
        self.betka_tmp_dir = TemporaryDirectory()
        self.clone_url: str = None
        self.betka_schema: Dict = {}
        self.image = None
        self.message = None
        self.msg_upstream_url: str = None
        self.upstream_git_path = None
        # Upstream cloned directory
        self.upstream_cloned_dir: Path = None
        # Upstream synced directory, from upstream cloned directory
        # Betka doesn't clone the same upstream repository more times then once
        self.upstream_synced_dir: Path = None
        self.upstream_hash = None
        self.downstream_dir: Path = None
        self.downstream_git_branch: str = None
        self.repo = None
        self.master_sync: bool = False
        self.pr_number = None
        self.pr_sync: bool = False
        self._github_api = self._pagure_api = None
        self.upstream_message: str = None
        self.upstream_pr_comment: str = None
        self.last_sync: int = 0
        self.headers = None
        self.betka_config: Dict = {}
        self.msg_artifact: Dict = {}
        self.timestamp_dir: Path = None
        self.config_json = load_config_json()
        self.readme_url = self.config_json["readme_url"]
        self.description = "Bot for syncing upstream to downstream"

    def set_config(self):
        """
        Set mandatory configuration values
        :return:
        """
        self.set_config_from_env(self.config_json["github_api_token"])
        self.set_config_from_env(self.config_json["pagure_user"])
        self.set_config_from_env("PROJECT")
        self.betka_config["pagure_api_token"] = os.environ[self.config_json["pagure_api_token"]]
        self.betka_config["new_api_version"] = bool(self.config_json["new_api_version"] == 'true')
        betka_url_base = self.config_json["betka_url_base"]
        if getenv("DEPLOYMENT") == "prod":
            self.betka_config["betka_yaml_url"] = f"{betka_url_base}betka-prod.yaml"
        else:
            self.betka_config[
                "betka_yaml_url"
            ] = f"{betka_url_base}betka-stage.yaml"
        self.headers = {
            "Authorization": "token " + self.betka_config.get("github_api_token")
        }

    @property
    def pagure_api(self):
        """
        Init GitHubAPI for working with Pagure
        :return:
        """
        if not self._pagure_api:
            self._pagure_api = PagureAPI(self.betka_config, self.config_json)
        return self._pagure_api

    @property
    def github_api(self):
        """
        Init GitHubAPI for working with GitHub PRs
        :return:
        """
        if not self._github_api:
            self._github_api = GitHubAPI(
                self.image,
                self.headers,
                Git.get_reponame_from_git_url(self.msg_upstream_url),
                Git.get_username_from_git_url(self.msg_upstream_url),
                self.config_json,
            )
        return self._github_api

    def log(self, level, msg, *args, **kwargs):
        """
        Overrides Bot.log() to log specific attributes of this bot.

        :param level: logging level as defined in logging module
        :param msg: message to log
        :param args: arguments to msg
        """
        report_dict: Dict = {
            "message": self.logger.format(msg, args),
            "master_sync": self.master_sync,
            "pr_sync": self.pr_sync,
            "upstream_hash": self.upstream_hash,
            "msg_upstream_url": self.msg_upstream_url,
            "downstream_pr": self.betka_schema.get("downstream_pr"),
        }
        self.logger.log(level, report_dict)

    def set_config_from_env(self, value):
        val = os.getenv(value)
        if val:
            self.betka_config[value.lower()] = val.strip()

    def refresh_betka_yaml(self):
        if time.time() > self.last_sync + SYNC_INTERVAL:
            self.betka_config.update(self.get_betka_yaml_config())
            self.last_sync = time.time()

    def get_betka_yaml_config(self):
        """
        Get betka main configuration file
        It is downloaded during betka start
        :return: dict
        """
        result = get(self.betka_config["betka_yaml_url"])
        result.raise_for_status()
        if result.status_code == 200:
            return yaml.safe_load(result.text)

    @staticmethod
    def load_yaml_configuration(path):
        """
        Load YAML file defined by path argument
        :param: path: Path to YAML configuration file
        :return: loaded yaml
        """
        return yaml.safe_load(open(path))

    def prepare_upstream_git(self):
        """
        Clone upstream git repository to self.upstream_cloned_dir
        :return:
        """
        self.upstream_cloned_dir = Git.clone_repo(
            self.msg_upstream_url, self.betka_tmp_dir.name
        )
        if self.upstream_cloned_dir is None:
            self.error("!!!! Cloning upstream repo %s FAILED.", self.msg_upstream_url)
            return False
        self.info("Upstream cloned directory %r", self.upstream_cloned_dir)
        return True

    def mandatory_variables_set(self):
        """
        Are mandatory default 'betka' values set ?
        :return: bool
        """
        if not self.betka_config.get("pagure_api_token"):
            self.error(
                "PAGURE_API_TOKEN variable has to be defined "
                "either in betka's global configuration file or as environment variable."
            )
            return False
        if not self.betka_config.get("github_api_token"):
            self.error(
                "GITHUB_API_TOKEN variable has to be defined "
                "either in betka's global configuration file or as environment variable."
            )
            return False
        if not self.betka_config.get("pagure_user"):
            self.error("pagure_user has to be specified because of working with forks")
            return False
        return True

    def send_umb_message_complete(self):
        pr_url = (
            f"{self.betka_schema.get('pagure', '')}/"
            f"{self.betka_schema.get('namespace_containers', '')}/"
            f"{self.betka_schema.get('downstream_repo', '')}/"
            f"pull-request/{self.betka_schema.get('pr_number', '')}"
        )
        result: Dict = {
            "url": pr_url,
            "pullrequest_id": self.betka_schema.get("pr_number", ""),
            "repository": f"{self.betka_schema.get('namespace_containers','')}/"
            f"{self.betka_schema.get('downstream_repo', '')}",
            "destination_branch": self.downstream_git_branch,
            "is_new": self.betka_schema.get("status") == "created",
        }
        UMBSender.send_umb_message_complete(self.msg_artifact, result)

    def sync_upstream_to_downstream_directory(self) -> bool:
        """
        Sync upstream directory to downstream directory.
        Use either upstream source code or generator
        defined in bot-cfg.yml
        :return: True - directory was synced
                 False - directory was not synced
        """
        image_url = self.config.get("image_url", None)

        if image_url:
            # Sources are generated by betka-generator
            # Results are stored in self.downstream_dir
            if not self.deploy_image(image_url):
                return False
        else:
            # Copy upstream into downstream. No betka-generator is called
            # Use root upstream directory if ups_path not defined
            ups_path = self.config.get("upstream_git_path")
            src_parent = (
                self.upstream_synced_dir
                if not ups_path
                else self.upstream_synced_dir / ups_path
            )
            copy_upstream2downstream(src_parent, self.downstream_dir)
        return True

    def send_result_email(self, betka_schema: Dict):
        """
        Send an email about results from master / pull request sync
        :return:
        """
        self.debug("betka_schema: %s", betka_schema)
        # Do not send email in case of pull request was not created
        if not self.betka_schema:
            return False
        betka_schema["downstream_git_branch"] = self.downstream_git_branch
        betka_schema["upstream_repo"] = self.msg_upstream_url

        email_message = text_from_template(
            template_dir=TEMPLATES,
            template_filename="email_template",
            template_data=betka_schema,
        )
        receivers = ["phracek@redhat.com"] + self.config.get("notifications", {}).get(
            "email_addresses", []
        )

        send_email(
            text=email_message,
            receivers=receivers,
            subject=f"[{NAME}] Upstream -> Downstream sync: {self.image}",
        )

    def sync_downstream_branches(self, branch) -> bool:
        """
        Sync upstream repository into relevant downstream dist-git branch
        based on the configuration file.
        :param branch: downstream branch to check and to sync
        """
        if not self.config.get("master_checker"):
            self.info("Syncing upstream repo to downstream repo is not allowed.")
            return False
        self.info(
            "Syncing upstream %r to downstream %r", self.msg_upstream_url, self.image
        )

        # Function checks if downstream contains pull request or not based on the title message
        title = self.betka_config["downstream_master_msg"]
        description_msg = COMMIT_MASTER_MSG.format(
            hash=self.upstream_hash, repo=self.repo
        )
        pr_id = self.pagure_api.check_downstream_pull_requests(
            msg_to_check=title,
            branch=branch
        )
        if not pr_id:
            Git.sync_fork_with_origin(self.pagure_api.full_downstream_url, branch)

        if not self.sync_upstream_to_downstream_directory():
            return False

        # git {add,commit,push} all files in local dist-git repo
        Git.git_add_all(
            upstream_msg=self.upstream_message,
            related_msg=Git.get_msg_from_jira_ticket(self.config))

        # Prepare betka_schema used for sending mail and Pagure Pull Request
        # The function also checks if downstream does not already contain pull request
        betka_schema = self.pagure_api.file_pull_request(
            title=title,
            pr_msg=description_msg,
            upstream_hash=self.upstream_hash,
            branch=branch,
            pr_id=pr_id,
        )
        self.send_result_email(betka_schema=betka_schema)
        return True

    def sync_pull_requests(self, branch) -> bool:
        """
        Sync upstream pr into downstream pr.
        :return: False if Pull Request is not synced
                 True if Pull Request is filed or updated
        """
        # Get all pull requests from upstream for correct image
        if not self.config.get("pr_checker"):
            self.info("Syncing upstream PR to downstream repo is not allowed.")
            return False

        # Get all upstream OPENED pull request
        pr_dict = self.github_api.get_pull_requests("OPEN")
        self.debug("pr_dict: %s", pr_dict)
        os.chdir(self.betka_tmp_dir.name)
        state = self.github_api.check_upstream_pr(self.pr_number)
        if state == "OPEN":
            # Commit message has to be the same as in the latest comment message
            comment = self.config.get("pr_comment_message")
            if not self.upstream_pr_comment.startswith(comment):
                return False
            os.chdir(str(self.upstream_synced_dir))
            Git.fetch_pr_origin(
                self.pr_number, f"Checkout to PR{self.pr_number} branch"
            )
            # Copy upstream directory into downstream directory
            title = f"{self.betka_config['downstream_pr_msg']} #{self.pr_number}"
            description_msg = COMMIT_PR_MSG.format(
                pr_num=self.pr_number, repo=self.repo
            )
            pr_id = self.pagure_api.check_downstream_pull_requests(title)

            os.chdir(str(self.downstream_dir))
            # Switch to downstream dist-git repo
            if not self.sync_upstream_to_downstream_directory():
                return False

            # git {add,commit,push} all files in local dist-git repo
            Git.git_add_all(self.upstream_message,
                            related_msg=Git.get_msg_from_jira_ticket(self.config))
            # Prepare betka_schema used for sending mail and Pagure Pull Request
            # The function also checks if downstream does not already contain pull request
            betka_schema = self.pagure_api.file_pull_request(
                title=title,
                pr_msg=description_msg,
                upstream_hash=self.upstream_hash,
                branch=branch,
                pr_id=pr_id,
                pr=True,
                pr_num=self.pr_number,
            )
            self.send_result_email(betka_schema=betka_schema)

        self.delete_close_merged_pull_requests()
        return True

    def delete_close_merged_pull_requests(self):
        """
        Delete or close or update already merged upstream Pull Requests.
        :param pr_dict: dictionary with relevant pull request
        # TODO document pr_dict
        """
        self.debug("delete_close_merged_pull_requests()")
        # Check for state of the upstream pull request.
        # If the upstream pull request was close/merged,
        # then updates the relevant downstream pull request
        state = self.github_api.check_upstream_pr(self.pr_number)
        if state != "OPEN":
            # If Upstream Pull Request is closed or merged, close also downstream
            # relevant Pull Request.
            msg_to_check = f"{self.betka_config['downstream_pr_msg']} #{self.pr_number}"
            # Checks downstream pull request according to upstream PR message.
            pr_id = self.pagure_api.check_downstream_pull_requests(
                msg_to_check, check_user=False
            )
            if pr_id:
                url_address = self.pagure_api.get_comment_url(self.repo, pr_id)
                link = "{url}/pull/{n}".format(
                    n=self.pr_number, url=Git.strip_dot_git(self.msg_upstream_url)
                )
                comment = (
                    f"Upstream PR {link} was {state}. "
                    f"This downstream PR {pr_id} can be closed. "
                    f"Feel free to close this upstream Pull Request."
                )
                data = {"comment": comment}
                # Updates downstream PR according to upstream PR.
                self.pagure_api.pagure_post_action(url_address, data)

    def get_synced_images(self) -> List:
        """
        Check if upstream url is mentioned in betka.yaml dist_git_repos variable.
        See betka.yaml for format.
        :return: list of synced images
        """
        synced_images = []
        for dist_git, upstream_urls in self.betka_config["dist_git_repos"].items():
            if upstream_urls[0] == self.msg_upstream_url:
                synced_images.append(dist_git)
        if not synced_images:
            return []
        return synced_images

    def deploy_image(self, image_url):

        # Sources are generated in another OpenShift POD
        self.debug("Starting OpenShift POD")
        from betka.openshift import OpenshiftDeployer

        self._copy_cloned_downstream_dir()
        di = OpenshiftDeployer(
            Git.get_reponame_from_git_url(self.msg_upstream_url),
            self.image,
            str(self.timestamp_dir),
            image_url,
            self.betka_config["project"],
        )
        result = di.deploy_image()
        results_dir = "results"
        list_dir_content(self.timestamp_dir / results_dir)
        if not result:
            return False

        copy_upstream2downstream(self.timestamp_dir / results_dir, self.downstream_dir)
        return True

    def get_pr_fedmsg_info(self, message):
        """
        Parse fedmsg message and check for proper values for pr_sync.
        :param message: fedmsg message
        :return: bool, True - message is ok, False - message is not ok
        """

        self.message = message
        # Example
        # https://apps.fedoraproject.org/datagrepper/raw?topic=org.fedoraproject.prod.github.issue.comment
        if not self.message.get("issue").get("pull_request"):
            self.info("The message is not for syncing Pull Request. Just issue comment")
            return False
        self.pr_number = self.message["issue"]["number"]
        self.pr_sync = True
        self.master_sync = False
        self.upstream_message = self.message["issue"]["title"]
        self.upstream_pr_comment = self.message["comment"]["body"]
        self.msg_artifact: Dict = {
            "type": "upstream-pr",
            "upstream_protal": "github.com",
            "issuer": self.message["issue"]["user"]["login"],
            "repository": self.message["repository"]["full_name"],
            "id": self.pr_number,
            "commit_hash": "",
            "comment_id": self.message["comment"]["id"],
            "uid": self.message["issue"]["id"],
        }
        return True

    def get_master_fedmsg_info(self, message):
        """
        Parse fedmsg message and check for proper values.
        :param message: fedmsg message
        :return: bool, True - message is ok, False - message is not ok
        """
        # Example
        # https://apps.fedoraproject.org/datagrepper/id?id=2018-ab4ad1f9-36a0-483a-9401-6b5c2a314383&is_raw=true&size=extra-large
        self.message = message
        if "head_commit" not in self.message or self.message["head_commit"] == "":
            self.info(
                "Fedora Messaging does not contain head_commit or is head_commit is empty %r",
                self.message,
            )
            return False
        href = self.message.get("ref")
        head_commit = self.message["head_commit"]
        if href != "refs/heads/master":
            self.info(f"Ignoring commit in non-master branch {href}.")
        self.upstream_hash = head_commit["id"]
        self.upstream_message = head_commit["message"]
        self.master_sync = True
        self.pr_sync = False
        self.msg_artifact: Dict = {
            "type": "upstream-push",
            "commit_hash": self.upstream_hash,
            "repository": self.message["repository"]["full_name"],
            "issuer": head_commit["author"]["name"],
            "upstream_portal": "github.com",
        }
        return True

    def prepare(self):
        """
        Load betka.yaml configuration, make ssh_wrapper
        and load init upstream repository configurations.
        :return: bool, True - success, False - some problem occurred
        """
        self.set_config()
        self.refresh_betka_yaml()
        if not self.betka_config.get("dist_git_repos"):
            self.error(
                f"Global configuration file {self.betka_config['betka_yaml_url']}"
                f" was not parsed properly"
            )
            return False

        if "pagure_api_token" in self.betka_config:
            self.betka_config["pagure_user"] = self.pagure_api.get_user_from_token()
        if not self.betka_config["pagure_user"]:
            self.error(
                f"Not able to get username from Internal Pagure "
                f"instance {self.config_json['pagure_host']}. See logs for details."
            )
            return False
        Git.create_dot_gitconfig(
            user_name=self.betka_config["pagure_user"], user_email="non@existing"
        )

        if not Git.has_ssh_access(self.config_json['pagure_host'], PAGURE_PORT,
                                  username=self.betka_config["pagure_user"]):
            self.error(f"SSH keys are not valid for {self.config_json['pagure_host']}.")
            return False

        if not self.mandatory_variables_set():
            return False

        try:
            self.msg_upstream_url = self.message["repository"]["html_url"]
        except KeyError:
            self.error(
                "Fedmsg does not contain html_url key" "in ['repository'] %r",
                self.message,
            )
            return False
        return True

    def prepare_downstream_git(self) -> bool:

        """
        Clone downstream dist-git repository, defined by self.clone_url variable
        and set `self.downstream_dir` variable.
        :returns True if downstream git directory was cloned
                 False if downstream git directory was not cloned
        """
        self.downstream_dir = Git.clone_repo(self.clone_url, self.betka_tmp_dir.name)
        self.info("Downstream directory %r", self.downstream_dir)
        if self.downstream_dir is None:
            self.error("!!!! Cloning downstream repo %s FAILED.", self.image)
            return False
        os.chdir(str(self.downstream_dir))
        return True

    def _copy_cloned_upstream_dir(self):
        """
        Copy cloned upstream directory stored in self.upstream_cloned_dir
        into upstream synced directory stored in self.upstream_synced_dir
        """
        self.upstream_synced_dir = self.timestamp_dir / Git.get_reponame_from_git_url(
            self.msg_upstream_url
        )
        if os.path.isdir(self.upstream_synced_dir):
            shutil.rmtree(self.upstream_synced_dir)
        shutil.copytree(
            str(self.upstream_cloned_dir), str(self.upstream_synced_dir), symlinks=True
        )

    def _copy_cloned_downstream_dir(self):
        """
        Copy cloned downstream directory stored in self.downstream_cloned_dir
        into downstream synced directory stored in self.downstream_synced_dir
        """
        self.downstream_synced_dir = self.timestamp_dir / "results"
        shutil.copytree(
            str(self.downstream_dir), str(self.downstream_synced_dir), symlinks=True
        )

    def _get_bot_cfg(self, branch: str) -> bool:
        Git.call_git_cmd(f"checkout {branch}", msg="Change downstream branch")
        try:
            self.config = self.pagure_api.get_bot_cfg_yaml(branch=branch)
            self.debug(f"Downstream 'bot-cfg.yml' file {self.config}.")
        except jsonschema.exceptions.ValidationError as jeverror:
            self.error(
                f"Getting bot.cfg {branch} from "
                f"{self.config_json['namespace_containers']}/{self.image} "
                f"failed. {jeverror.message}"
            )
            raise
        return True

    def delete_timestamp_dir(self):
        """
        Check if self.timestamp_dir is defined and it is the directory
        """
        if self.timestamp_dir and self.timestamp_dir.is_dir():
            shutil.rmtree(str(self.timestamp_dir))

    def delete_cloned_directories(self):
        """
        Delete synced and temporary directory
        """
        self.debug("Remove timestamp and upstream cloned directories.")
        self.delete_timestamp_dir()
        if self.upstream_cloned_dir.is_dir():
            shutil.rmtree(str(self.upstream_cloned_dir))

    def create_and_copy_timestamp_dir(self):
        """
        Creates self.timestamp_dir and copy upstream_dir into it
        :return:
        """
        timestamp_id = (
            f"{datetime.now().strftime('%Y%m%d%H%M%S')}-"
            f"{Git.get_reponame_from_git_url(self.msg_upstream_url)}"
        )
        self.timestamp_dir = Path(GENERATOR_DIR) / timestamp_id
        self._copy_cloned_upstream_dir()

    def _sync_valid_branches(self, valid_branches):
        """
        Syncs valid branches in namespace
        :param valid_branches: valid branches to sync
        :return:
        """
        try:
            self.prepare_upstream_git()
        except subprocess.CalledProcessError:
            self.error(f"!!!! Cloning upstream repo {self.msg_upstream_url} FAILED")
            raise
        for branch in valid_branches:
            self.timestamp_dir: Path = None
            self.downstream_git_branch = branch
            # This loads downstream bot-cfg.yml file
            # and update betka's dictionary (self.config).
            # We need to have information up to date

            if not self._get_bot_cfg(branch=self.downstream_git_branch):
                continue
            # Gets repo url without .git for cloning
            self.repo = Git.strip_dot_git(self.msg_upstream_url)
            if self.master_sync:
                self.info("SYNCING UPSTREAM TO DOWNSTREAM.")
                if not self.config.get("master_checker"):
                    self.info(
                        "Syncing upstream repo to downstream repo is not allowed."
                    )
                    continue
                self.create_and_copy_timestamp_dir()
                self.sync_downstream_branches(self.downstream_git_branch)
            elif self.pr_sync:
                self.info("SYNCING UPSTREAM PR TO DOWNSTREAM PR.")
                # Get all pull requests from upstream for correct image
                if not self.config.get("pr_checker"):
                    self.info("Syncing upstream PR to downstream repo is not allowed.")
                    continue
                self.create_and_copy_timestamp_dir()
                if self.sync_pull_requests(self.downstream_git_branch):
                    # Updates pull request from downstream
                    self.delete_close_merged_pull_requests()
            self.delete_timestamp_dir()

    def run_sync(self):
        """
        Execute betka either for master sync from upstream repository into a downstream dist-git
        repository or pull request sync from upstream pull request into a downstream pull request
        """
        UMBSender.send_umb_message_in_progress(self.msg_artifact)
        try:
            self._run_sync()
        except Exception as ex:
            text = (
                f"{str(traceback.format_exc())}\n"
                f"Locals:\n{pformat(locals())}\nGlobals:\n{pformat(globals())}"
            )
            UMBSender.send_umb_message_error(self.msg_artifact, str(ex), text, url=None)
            raise ex

    def _run_sync(self):
        self.refresh_betka_yaml()
        for self.image in self.get_synced_images():
            self.pagure_api.set_image(self.image)
            # Checks if pagure already contains a fork for the image self.image
            # The image name is defined in the betka.yaml configuration file
            # variable dist_git_repos
            if not self.pagure_api.get_pagure_fork():
                UMBSender.send_umb_message_skip(
                    self.msg_artifact, "not-applicable", "pagure fork not found"
                )
                continue

            self.info("Trying to sync image %r.", self.image)
            os.chdir(self.betka_tmp_dir.name)

            self.clone_url = self.pagure_api.get_clone_url()
            if not self.prepare_downstream_git():
                UMBSender.send_umb_message_skip(
                    self.msg_artifact,
                    "not-applicable",
                    "Failed cloning downstream repository",
                )
                continue

            valid_branches = self.pagure_api.get_valid_branches(self.downstream_dir)
            if not valid_branches:
                msg = "There are no valid branches with bot-cfg.yaml file"
                self.info(msg)
                UMBSender.send_umb_message_skip(
                    self.msg_artifact, "not-applicable", msg
                )
                if self.downstream_dir.is_dir():
                    shutil.rmtree(str(self.downstream_dir))
                continue

            try:
                self._sync_valid_branches(valid_branches)
            finally:
                self.delete_cloned_directories()

            self.send_umb_message_complete()

        # Deletes temporary directory.
        # It is created during each upstream2downstream task.
        if Path(self.betka_tmp_dir.name).is_dir():
            self.betka_tmp_dir.cleanup()
