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
import requests

from os import getenv
from datetime import datetime
from tempfile import TemporaryDirectory
from pprint import pformat
from pathlib import Path
from typing import Dict, List, Any

from betka.bot import Bot
from betka.emails import BetkaEmails
from betka.utils import text_from_template, SlackNotifications
from betka.git import Git
from betka.github import GitHubAPI
from betka.utils import copy_upstream2downstream
from betka.gitlab import GitLabAPI
from betka.exception import BetkaNetworkException, BetkaNetworkException
from betka.constants import (
    GENERATOR_DIR,
    COMMIT_MASTER_MSG,
    NAME,
    TEMPLATES,
    SYNC_INTERVAL,
)
from betka.utils import FileUtils
from betka.named_tuples import ProjectMR, ProjectFork, ProjectInfo


requests.packages.urllib3.disable_warnings()


class Betka(Bot):

    cfg_key = "upstream-to-downstream"

    def __init__(self, task_name=None):
        super().__init__(task_name=task_name)
        self.betka_tmp_dir = TemporaryDirectory()
        self.ssh_url_to_repo: str = None
        self.betka_schema: Dict = {}
        self.image = None
        self.project_id: int = 0
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
        self.downstream_git_origin_branch: str = None
        self.repo = None
        self.pr_number = None
        self._github_api = self._gitlab_api = None
        self.upstream_message: str = None
        self.upstream_pr_comment: str = None
        self.last_sync: int = 0
        self.headers = None
        self.betka_config: Dict = {}
        self.msg_artifact: Dict = {}
        self.timestamp_dir: Path = None
        self.config_json = None
        self.readme_url = ""
        self.description = "Bot for syncing upstream to downstream"

    def set_environment_variables(self):
        for variable in ["PROJECT", "DEVEL_MODE", "GITHUB_API_TOKEN", "GITLAB_USER", "GITLAB_API_TOKEN"]:
            self.set_config_from_env(variable)

    def set_config(self):
        """
        Set mandatory configuration values
        :return:
        """
        if "slack_webhook_url" in self.config_json:
            self.set_config_from_env(self.config_json["slack_webhook_url"])
        self.betka_config["generator_url"] = self.config_json["generator_url"]
        if "use_gitlab_forks" not in self.config_json:
            self.betka_config["use_gitlab_forks"] = False
        else:
            self.betka_config["use_gitlab_forks"] = self.config_json["use_gitlab_forks"]
        betka_url_base = self.config_json["betka_url_base"]
        if getenv("DEPLOYMENT") == "prod":
            self.betka_config["betka_yaml_url"] = f"{betka_url_base}betka-prod.yaml"
        else:
            self.betka_config["betka_yaml_url"] = f"{betka_url_base}betka-stage.yaml"
        self.headers = {
            "Authorization": "token " + self.betka_config.get("github_api_token")
        }

    @property
    def gitlab_api(self):
        """
        Init GitHubAPI for working with Pagure
        :return:
        """
        if not self._gitlab_api:
            self._gitlab_api = GitLabAPI(self.betka_config, self.config_json)
        return self._gitlab_api

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
        result = requests.get(self.betka_config["betka_yaml_url"], verify=False)
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

    def is_fork_enabled(self):
        value = self.betka_config["use_gitlab_forks"].lower()
        if value in ["true", "yes"]:
            return True
        return False

    def mandatory_variables_set(self):
        """
        Are mandatory default 'betka' values set ?
        :return: bool
        """
        if not self.betka_config.get("gitlab_api_token"):
            self.error(
                "GITLAB_API_TOKEN variable has to be defined "
                "either in betka's global configuration file or as environment variable."
            )
            return False
        if not self.betka_config.get("github_api_token"):
            self.error(
                "GITHUB_API_TOKEN variable has to be defined "
                "either in betka's global configuration file or as environment variable."
            )
            return False
        if not self.betka_config.get("gitlab_user"):
            self.error("gitlab_user has to be specified because of working with forks")
            return False
        return True

    def _get_image_url(self) -> Any:
        image_url = self.betka_config.get("generator_url", None)
        self.debug(f"Image generator url from betka_config: {image_url}")
        if not image_url:
            image_url = self.config.get("image_url", None)
        return image_url

    def sync_upstream_to_downstream_directory(self) -> bool:
        """
        Sync upstream directory to downstream directory.
        Use either upstream source code or generator
        defined in bot-cfg.yml
        :return: True - directory was synced
                 False - directory was not synced
        """
        image_url = self._get_image_url()

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
            if not src_parent.exists():
                self.error(f"Upstream path {ups_path} for {self.image} does not exist. "
                           f"Check betka configuration file for version validity.")
                BetkaEmails.send_email(
                    text=f"Upstream path {ups_path} for {self.image} does not exist. "
                         f"Check betka configuration file for version validity.",
                    receivers=["phracek@redhat.com"],
                    subject=f"[betka-run-sync] Upstream path {ups_path} for {self.image} does not exist.",
                )
                return True
            copy_upstream2downstream(src_parent, self.downstream_dir)
        return True

    def slack_notification(self):
        if "slack_webhook_url" not in self.betka_config:
            self.info(
                "No slack webhook url provided in config.json file, skipping slack notifications."
            )
            return False
        url = self.betka_config.get("slack_webhook_url", None)
        if url is None or url == "":
            self.info("No slack webhook url provided, skipping slack notifications.")
            return False
        project_mr: ProjectMR = self.betka_schema["merge_request_dict"]
        message = f"Sync <{project_mr.web_url}|{self.image} MR#{project_mr.iid}>: *{project_mr.title}*"
        SlackNotifications.send_webhook_notification(url=url, message=message)
        return True

    def get_config_emails(self) -> List[str]:
        if "notifications" not in self.config:
            return []
        if "email_addresses" not in self.config.get("notifications"):
            return []
        return self.config.get("notifications", {}).get("email_addresses", [])

    def send_result_email(self, betka_schema: Dict):
        """
        Send an email about results from master / pull request sync
        :return:
        """
        self.betka_schema.update(betka_schema)
        self.debug("betka_schema: %s", self.betka_schema)
        # Do not send email in case of pull request was not created
        if not self.betka_schema:
            return False
        if not self.slack_notification():
            self.debug("Sending notification was not successful.")
        self.betka_schema["downstream_git_branch"] = self.downstream_git_branch
        self.betka_schema["upstream_repo"] = self.msg_upstream_url
        self.betka_schema["namespace"] = self.config_json["gitlab_namespace"]

        email_message = text_from_template(
            template_dir=TEMPLATES,
            template_filename="email_template",
            template_data=self.betka_schema,
        )
        receivers = ["phracek@redhat.com"]
        additional_emails = self.get_config_emails()
        if additional_emails:
            receivers += additional_emails
        self.debug(f"Receivers: {receivers}")

        BetkaEmails.send_email(
            text=email_message,
            receivers=receivers,
            subject=f"[{NAME}] Upstream -> Downstream sync: {self.image}",
        )
        return True

    def sync_to_downstream_branches(self, branch, origin_branch: str = "") -> Any:
        """
        Sync upstream repository into relevant downstream dist-git branch
        based on the configuration file.
        :param branch: downstream branch to check and to sync
        """
        self.info(f"Syncing upstream {self.msg_upstream_url} to downstream {self.image}")
        mr = self.gitlab_api.check_gitlab_merge_requests(branch=branch, target_branch=origin_branch)
        if not mr and self.is_fork_enabled():
            Git.get_changes_from_distgit(url=self.gitlab_api.get_forked_ssh_url_to_repo())
            Git.push_changes_to_fork(branch=branch)

        if not self.sync_upstream_to_downstream_directory():
            return False

        # git {add,commit,push} all files in local dist-git repo
        git_status = Git.git_add_all(
            upstream_msg=self.upstream_message,
            related_msg=Git.get_msg_from_jira_ticket(self.config),

        )
        if not git_status:
            self.info(
               f"There were no changes in repository. Do not file a pull request."
            )
            BetkaEmails.send_email(
                text=f"There were no changes in repository {self.image} to {branch}. Fork status {self.is_fork_enabled()}.",
                receivers=["phracek@redhat.com"],
                subject="[betka-diff] No git changes",
            )
            return False
        return mr

    def update_gitlab_merge_request(self, mr: ProjectMR, branch, origin_branch: str = ""):
        self.debug(f"update_gitlab_merge_request: Devel mode is enabled: {self.betka_config['devel_mode']}")
        if self.betka_config["devel_mode"] == "true":
            BetkaEmails.send_email(
                text="Devel mode is enabled. See logs in devel project.",
                receivers=["phracek@redhat.com"],
                subject="[betka-devel] Devel mode is enabled.",
            )
            return False
        description_msg = COMMIT_MASTER_MSG.format(
            hash=self.upstream_hash, repo=self.repo
        )
        git_push_status = Git.git_push(fork_enabled=self.is_fork_enabled(), source_branch=branch)
        if not git_push_status:
            self.info(
               f"Pushing to dist-git was not successful {branch}. Original_branch {origin_branch}."
            )
            BetkaEmails.send_email(
                text=f"Pushing to {branch}. See logs from the bot.",
                receivers=["phracek@redhat.com"],
                subject="[betka-push] Pushing was not successful.",
            )
            return False
        # Prepare betka_schema used for sending mail and Pagure Pull Request
        # The function also checks if downstream does not already contain pull request
        betka_schema = self.gitlab_api.file_merge_request(
            pr_msg=description_msg,
            upstream_hash=self.upstream_hash,
            branch=branch,
            mr=mr,
            origin_branch=origin_branch,
        )
        self.send_result_email(betka_schema=betka_schema)
        return True

    def get_synced_images(self) -> Dict:
        """
        Check if upstream url is mentioned in betka.yaml dist_git_repos variable.
        See betka.yaml for format.
        :return: dict of synced images in format image_name: project_id
        """
        synced_images = {}
        for key in self.betka_config["dist_git_repos"]:
            values = self.betka_config["dist_git_repos"][key]
            if values["url"] != self.msg_upstream_url:
                continue
            synced_images[key] = values
            self.debug(f"Synced images {synced_images}.")
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
        if not result:
            return False
        results_dir = "results"
        FileUtils.list_dir_content(self.timestamp_dir / results_dir)

        copy_upstream2downstream(self.timestamp_dir / results_dir, self.downstream_dir)
        return True

    def get_master_fedmsg_info(self, message):
        """
        Parse fedmsg message and check for proper values.
        :param message: fedmsg message
        :return: bool, True - message is ok, False - message is not ok
        """
        # Example
        # https://apps.fedoraproject.org/datagrepper/id?id=2018-ab4ad1f9-36a0-483a-9401-6b5c2a314383&is_raw=true&size=extra-large
        self.message = message.get("body")
        href = self.message.get("ref")
        if not (href == "refs/heads/master" or href == "refs/heads/main"):
            return False
        if "repository" in self.message:
            self.debug(f"Repository in message: {self.message.get('repository')}")
        self.upstream_hash = self.message.get("after")
        if "head_commit" not in self.message:
            self.debug(f"head_commit is not present in {self.message}")
            return False
        head_commit = self.message.get("head_commit")
        self.debug(f"Repository in message: {head_commit}")
        self.upstream_message = head_commit["message"]
        self.msg_artifact: Dict = {
            "type": "upstream-push",
            "commit_hash": self.upstream_hash,
            "repository": self.message["repository"]["full_name"],
            "issuer": head_commit["author"]["name"],
            "upstream_portal": "github.com",
        }
        #self.debug(f"Message artifacts {self.msg_artifact}")
        return True

    def prepare(self):
        """
        Load betka.yaml configuration, make ssh_wrapper
        and load init upstream repository configurations.
        :return: bool, True - success, False - some problem occurred
        """
        self.config_json = FileUtils.load_config_json()
        self.set_environment_variables()
        self.set_config()
        self.readme_url = self.config_json["readme_url"]
        self.refresh_betka_yaml()
        if not self.betka_config.get("dist_git_repos"):
            self.error(
                f"Global configuration file {self.betka_config['betka_yaml_url']} was not parsed properly"
            )
            return False
        if "gitlab_api_token" not in self.betka_config:
            self.error(
                f"Global configuration file {self.betka_config['betka_yaml_url']} "
                "does not have defined GITLAB_API_TOKEN."
            )
            BetkaEmails.send_email(
                text=f"Global configuration file {self.betka_config['betka_yaml_url']} "
                "does not have defined GITLAB_API_TOKEN. See for more info to bot logs.",
                receivers=["phracek@redhat.com"],
                subject="[betka-prepare] Preparation task failed.",
            )
            return False

        if "gitlab_api_token" in self.betka_config:
            current_user = self.gitlab_api.check_authentication()
            if not current_user:
                BetkaEmails.send_email(
                    text="GitLab authentication failed. See logs from the bot.",
                    receivers=["phracek@redhat.com"],
                    subject="[betka-prepare] Preparation task failed.",
                )
                return False
            self.betka_config["gitlab_user"] = current_user.username

        if not self.betka_config["gitlab_user"]:
            self.error("Not able to get username from Gitlab. See logs for details.")
            return False

        Git.create_dot_gitconfig(
            user_name=self.betka_config["gitlab_user"], user_email="non@existing"
        )

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

    def prepare_fork_downstream_git(self, project_fork: ProjectFork) -> bool:

        """
        Clone downstream dist-git repository, defined by self.ssh_url_to_repo variable
        and set `self.downstream_dir` variable.
        :returns True if downstream git directory was cloned
                 False if downstream git directory was not cloned
        """
        self.downstream_dir = Git.clone_repo(
            project_fork.ssh_url_to_repo, self.betka_tmp_dir.name
        )
        self.info("Downstream directory %r", self.downstream_dir)
        if self.downstream_dir is None:
            self.error("!!!! Cloning downstream repo %s FAILED.", self.image)
            return False
        os.chdir(str(self.downstream_dir))
        # This function updates fork based on the upstream
        Git.get_changes_from_distgit(url=self.gitlab_api.get_forked_ssh_url_to_repo())

        return True

    def prepare_downstream_git(self, project_info: ProjectInfo) -> bool:

        """
        Clone downstream dist-git repository, defined by self.ssh_url_to_repo variable
        and set `self.downstream_dir` variable.
        :returns True if downstream git directory was cloned
                 False if downstream git directory was not cloned
        """
        self.downstream_dir = Git.clone_repo(
            project_info.ssh_url_to_repo, self.betka_tmp_dir.name
        )
        self.info(f"Downstream directory {self.downstream_dir}")
        if self.downstream_dir is None:
            self.error("!!!! Cloning downstream repo %s FAILED.", self.image)
            return False
        os.chdir(str(self.downstream_dir))
        # This function updates fork based on the upstream

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

    def _get_bot_cfg(self, branch: str = "main") -> bool:
        # Use bot-cfg.yml from cloned directory
        with open(f"{str(self.downstream_dir)}/bot-cfg.yml") as stream:
            self.config = yaml.safe_load(stream)
        # self.config = self.gitlab_api.get_bot_cfg_yaml(branch=branch)
        self.debug(f"Downstream 'bot-cfg.yml' file '{self.config}'.")
        if not self.config:
            self.error(
                f"Getting bot.cfg {branch} from "
                f"{self.config_json['gitlab_namespace']}/{self.image} failed."
            )
            raise BetkaNetworkException("Config does not exists or it is wrong.")
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

    def _update_valid_branches(self):
        # Branches are taken from upstream repository like
        # https://src.fedoraproject.org/container/nginx not from fork
        all_branches = self.gitlab_api.get_branches()
        # Filter our branches before checking bot-cfg.yml files
        branch_list_to_sync = Git.branches_to_synchronize(
            self.betka_config, all_branches=all_branches
        )
        self.debug(f"Branches to sync {branch_list_to_sync}")
        Git.sync_fork_with_upstream(branch_list_to_sync)
        return branch_list_to_sync

    def _get_valid_origin_branches(self):
        if self.is_fork_enabled():
            all_branches = Git.get_valid_remote_branches()
        else:
            all_branches = Git.get_valid_remote_branches(default_string="remotes/origin/")
        self.debug(f"All remote branches {all_branches}.")
        # Filter our branches before checking bot-cfg.yml files
        branch_list_to_sync = Git.branches_to_synchronize(
            self.betka_config, all_branches=all_branches
        )
        self.debug(f"Branches to sync {branch_list_to_sync}")
        return branch_list_to_sync

    def _update_valid_remote_branches(self):
        # Branches are taken from upstream repository like
        # https://src.fedoraproject.org/container/nginx not from fork
        branch_list_to_sync = self._get_valid_origin_branches()
        Git.sync_fork_with_upstream(branch_list_to_sync)
        return branch_list_to_sync

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
            if self.is_fork_enabled():
                self.downstream_git_branch = branch
                self.downstream_git_origin_branch = ""
                Git.call_git_cmd(f"checkout {branch}", msg="Change downstream branch")
            else:
                self.downstream_git_branch = f"betka-{datetime.now().strftime('%Y%m%d%H%M%S')}-{branch}"
                self.downstream_git_origin_branch = branch
                Git.call_git_cmd(
                    f"checkout -b {self.downstream_git_branch} --track origin/{branch}",
                    msg="Create a new downstream branch"
                )
            try:
                if not self._get_bot_cfg(branch=branch):
                    self.error("Fetching bot-cfg.yaml failed.")
                    BetkaEmails.send_email(
                        text=f"Get 'bot-cfg.yml' for {self.image} and {branch} were not read properly or does not exist."
                             f"by upstream2downstream-bot.\n"
                             f"Inform phracek@redhat.com",
                        receivers=["phracek@redhat.com"],
                        subject=f"[betka-sync] Get 'bot-cfg' for {self.image} and {branch} does not exist or is wrong.",
                    )
                    continue
            except BetkaNetworkException as bne:
                self.debug(f"Betka Network Exception: {bne}.")
                continue
            except requests.exceptions.HTTPError as htpe:
                self.debug(f"HTTPError: It looks like URL is not valid: {htpe}.")
                continue

            # Gets repo url without .git for cloning
            self.repo = Git.strip_dot_git(self.msg_upstream_url)
            self.info("SYNCING UPSTREAM TO DOWNSTREAM.")
            # if not self.config.get("master_checker"):
            #     continue
            self.create_and_copy_timestamp_dir()
            mr: ProjectMR = self.sync_to_downstream_branches(
                self.downstream_git_branch, self.downstream_git_origin_branch
            )
            self.update_gitlab_merge_request(
                    mr=mr, branch=self.downstream_git_branch, origin_branch=self.downstream_git_origin_branch
            )
            self.delete_timestamp_dir()

    def run_sync(self):
        """
        Execute betka either for master sync from upstream repository into a downstream dist-git
        repository or pull request sync from upstream pull request into a downstream pull request
        """
        try:
            self._run_sync()
        except Exception as ex:
            text = (
                f"{str(traceback.format_exc())}\n"
                f"Locals:\n{pformat(locals())}\nGlobals:\n{pformat(globals())}"
            )
            raise ex

    def _run_sync(self):
        self.refresh_betka_yaml()
        list_synced_images = self.get_synced_images()
        if list_synced_images:
            self.debug(f"Let's sync these images {list_synced_images}")
        for self.image, values in list_synced_images.items():
            self.gitlab_api.set_variables(image=self.image)
            # Checks if gitlab already contains a fork for the image self.image
            # The image name is defined in the betka.yaml configuration file
            # variable dist_git_repos

            try:
                project_id = self.gitlab_api.get_project_id_from_url()
            except requests.exceptions.HTTPError as htpe:
                BetkaEmails.send_email(
                    text=f"Get project from URL {self.image} were not successful"
                    f"by upstream2downstream-bot. See {values} {htpe.response}\n"
                    f"Inform phracek@redhat.com",
                    receivers=["phracek@redhat.com"],
                    subject=f"[betka-sync] Get project from URL project {self.image} were not successful.",
                )
                continue
            if self.is_fork_enabled():
                self.gitlab_api.init_projects()
                project_fork = self.gitlab_api.check_and_create_fork()
                if not project_fork:
                    BetkaEmails.send_email(
                        text=f"Fork for project {self.image} were not successful"
                        f"by upstream2downstream-bot. See {values}\n"
                        f"Inform phracek@redhat.com",
                        receivers=["phracek@redhat.com"],
                        subject=f"[betka-sync] Fork for project {self.image} were not successful.",
                    )
                    continue
                self.ssh_url_to_repo = project_fork.ssh_url_to_repo
                self.debug(f"Clone URL is: {self.ssh_url_to_repo}")
                os.chdir(self.betka_tmp_dir.name)
                if not self.prepare_fork_downstream_git(project_fork):
                    continue
                branch_list_to_sync = self._update_valid_remote_branches()
            else:
                self.gitlab_api.init_projects()
                project_info = self.gitlab_api.get_project_info()
                self.ssh_url_to_repo = project_info.ssh_url_to_repo
                self.debug(f"Clone URL is: {self.ssh_url_to_repo}")
                os.chdir(self.betka_tmp_dir.name)
                if not self.prepare_downstream_git(project_info):
                    continue
                branch_list_to_sync = self._get_valid_origin_branches()
            self.info(
                f"Trying to sync image {self.image} to GitLab project_id {self.gitlab_api.project_id}."
            )

            valid_branches = Git.get_valid_branches(
                self.image, self.downstream_dir, branch_list_to_sync
            )

            if not valid_branches:
                msg = "There are no valid branches with bot-cfg.yaml file"
                self.info(msg)
                if self.downstream_dir.is_dir():
                    shutil.rmtree(str(self.downstream_dir))
                continue

            try:
                self._sync_valid_branches(valid_branches)
            finally:
                self.delete_cloned_directories()

        # Deletes temporary directory.
        # It is created during each upstream2downstream task.
        if Path(self.betka_tmp_dir.name).is_dir():
            self.betka_tmp_dir.cleanup()
