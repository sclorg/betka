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
import subprocess

from urllib.parse import urlparse
from logging import getLogger
from pathlib import Path
from subprocess import CalledProcessError
from typing import Dict, List

from betka.utils import run_cmd
from betka.constants import SYNCHRONIZE_BRANCHES, DOWNSTREAM_CONFIG_FILE

logger = getLogger(__name__)


class Git(object):
    @staticmethod
    def has_ssh_access(url: str, port: None, username=None) -> bool:
        """
        Check if SSH keys are able to push changes into Pagure
        :param url: Pagure URL address
        :param port: port for checking SSH keys
        :param username: specify username if port is not defined
        :return: False if SSH keys are not valid for Pagure
                 True if SSH Keys are valid for using with Pagure
        """
        cmd = f"ssh -T git@git.{url} -p {port}"
        if not port:
            cmd = f"ssh -T {username}@pkgs.fedoraproject.org"
        retval = run_cmd(cmd.split())
        return retval == 0

    @staticmethod
    def update_upstream_msg(upstream_msg):
        if isinstance(upstream_msg, list):
            msg = [msg.replace("'", "\'") for msg in upstream_msg]
        else:
            msg = upstream_msg.replace("'", "\'")
        return msg

    @staticmethod
    def git_add_all(upstream_msg: str, related_msg: str) -> bool:
        """
        Add and push all files into the fork.
        :param upstream_msg:
        :param related_msg:
        :param fork_enabled:
        :param source_branch:
        """
        git_show_status = Git.call_git_cmd(
           "diff HEAD", ignore_error=True, msg="Check git status"
        )
        logger.debug(f"Show git diff {git_show_status}")
        Git.call_git_cmd("add -A", msg="Add all")

        upstream_msg += f"\n{related_msg}\n"
        try:
            upstream_msg = Git.update_upstream_msg(upstream_msg)
            commit_msg = " ".join(
                [f"-m '{msg}'" for msg in upstream_msg.split("\n") if msg != ""]
            )
            status = Git.call_git_cmd(
                f"commit {commit_msg}",
                msg="Commit into distgit",
                return_output=False,
                ignore_error=True,
            )
            if status != 0:
                logger.info("Downstream repository was NOT changed. NOTHING TO COMMIT.")
                return False
        except CalledProcessError:
            pass
        return True

    @staticmethod
    def git_push(fork_enabled: bool = False, source_branch: str = "") -> bool:

        if fork_enabled:
            try:
                Git.call_git_cmd("push", msg="Push changes into git")
            except CalledProcessError:
                return False
        else:
            try:
                Git.call_git_cmd(f"push -u origin {source_branch}", msg="Push changes into git")
            except CalledProcessError:
                return False
        return True

    @staticmethod
    def clone_repo(clone_url: str, tempdir: str) -> Path:
        """
        Clone git repository from url.
        :param clone_url: url to clone from, it can also be a local path (directory)
        :param tempdir: temporary directory, where the git is cloned
        :return: directory with cloned repo or None
        """
        # clone_url can be url as well as path to directory, try to get the last part (strip .git)
        reponame = Git.strip_dot_git(clone_url.split("/")[-1])
        cloned_dir = Path(tempdir) / reponame
        clone_success = True
        try:
            Git.call_git_cmd(
                f"clone --recurse-submodules {clone_url} {str(cloned_dir)}"
            )
        except CalledProcessError:
            # clone git repository w/o submodule. In case submodules does not exist
            clone_success = False
        if not clone_success:
            try:
                Git.call_git_cmd(f"clone {clone_url} {str(cloned_dir)}")
            except CalledProcessError:
                raise
        return cloned_dir

    @staticmethod
    def fetch_pr_origin(number: str, msg: str):
        """
        Fetch specific Pull Request.
        :param number: PR number to fetch
        :param msg: message shown in log file
        """
        # Download Upstream repo to temporary directory
        # 'git fetch origin pull/ID/head:BRANCHNAME or git checkout origin/pr/ID'
        Git.call_git_cmd("fetch origin pull/{n}/head:PR{n}".format(n=number), msg=msg)

    @staticmethod
    def get_changes_from_distgit(url: str) -> str:
        """
        Sync fork with the latest changes from downstream origin.
        * Add downstream origin and upstream
        * fetch upstream
        :param url: Str: URL which is adds upstream into origin
        """
        Git.call_git_cmd("remote -v")
        remote_defined: bool = False
        try:
            remote_defined = Git.call_git_cmd("config remote.upstream.url")
        except subprocess.CalledProcessError:
            pass
        # add git remote upstream if it is not defined
        if not remote_defined:
            Git.call_git_cmd(f"remote add upstream {url}")
        all_braches = Git.call_git_cmd("remote update upstream")
        return all_braches

    @staticmethod
    def push_changes_to_fork(branch: str):
        """
        Push changes into dist_git branch
        * Reset commit with the latest downstream origin
        * push changes back to origin
        :param branch: str: Name of branch to sync
        """
        Git.call_git_cmd(f"reset --hard upstream/{branch}")
        Git.call_git_cmd(f"push origin {branch} --force")

    @staticmethod
    def get_valid_remote_branches(default_string: str = "remotes/upstream/") -> List[str]:
        remote_branches = []
        all_branches = Git.get_all_branches()
        for branch in all_branches.split("\n"):
            branch = branch.strip()
            if branch.startswith(default_string):
                new_branch = branch.replace(default_string, "")
                remote_branches.append(new_branch)
        return remote_branches

    @staticmethod
    def get_all_branches() -> str:
        """
        Returns list of all branches as for origin as for upstream
        :return: List of all branches
        """
        return Git.call_git_cmd("branch -a", return_output=True)

    @staticmethod
    def get_msg_from_jira_ticket(config: Dict) -> str:
        """
        :param config: Dict: Container configuration file
        :return: str: msg for commit. Empty if config does not contain "jira_config" field
                "Related: rhbz#<number> if "jira_config" is number
                "Related: jira_ticket if "jira_config" has a format "RHELPLAN-number"
        """
        if "jira_ticket" not in config:
            return ""

        jira_ticket = config.get("jira_ticket")
        try:
            # Check if jira_ticket is number
            int(jira_ticket)
            return f"Related: rhbz#{jira_ticket}"
        except ValueError:
            # jira_ticket is string
            pass

        if jira_ticket.startswith("RHELPLAN-"):
            return f"Related: {jira_ticket}"
        return ""

    @staticmethod
    def sync_fork_with_upstream(branches_to_sync):
        for brn in branches_to_sync:
            try:
                logger.debug(f"Let's try to checkout to {brn} branch.")
                Git.call_git_cmd(f"checkout -b {brn} upstream/{brn}")
            except subprocess.CalledProcessError:
                pass
            Git.call_git_cmd(f"push origin {brn} --force")

    @staticmethod
    def branches_to_synchronize(
        betka_config: Dict, all_branches: List[str]
    ) -> List[str]:
        """
        Checks if branch mentioned in betka configuration file
        is mentioned in valid_branches
        :return: list of valid branches to sync
        """
        synchronize_branches = tuple(betka_config.get(SYNCHRONIZE_BRANCHES, []))
        return [b for b in all_branches if b in synchronize_branches]

    @staticmethod
    def call_git_cmd(
        cmd, return_output=True, ignore_error=False, msg=None, git_dir=None, shell=True
    ):
        """
        Runs the GIT command with specified arguments
        :param cmd: list or string, git subcommand for execution
        :param return_output: bool, return output of the command ?
        :param ignore_error: bool, do not fail in case nonzero return code
        :param msg: log this before running the command
        :param git_dir: run the command in another directory
        :param shell: bool, run git commands in shell by default
        :return: output of the git command
        """
        if msg:
            logger.info(msg)

        command = "git"
        # use git_dir as work-tree git parameter and git-dir parameter (with added git.postfix)
        if git_dir:
            command += f" --git-dir {git_dir}/.git"
            command += f" --work-tree {git_dir}"
        if isinstance(cmd, str):
            command += f" {cmd}"
        elif isinstance(cmd, list):
            command += f" {' '.join(cmd)}"
        else:
            raise ValueError(f"{cmd} is not a list nor a string")

        output = run_cmd(
            command, return_output=return_output, ignore_error=ignore_error, shell=shell
        )
        logger.debug(output)
        return output

    """Class for working with git."""

    @staticmethod
    def parse_git_repo(potential_url):
        """Cover the following variety of URL forms for Github/Gitlab repo referencing.

        1) www.domain.com/foo/bar
        2) (same as above, but with ".git" in the end)
        3) (same as the two above, but without "www.")
        # all of the three above, but starting with "http://", "https://", "git://", "git+https://"
        4) git@domain.com:foo/bar
        5) (same as above, but with ".git" in the end)
        6) (same as the two above but with "ssh://" in front or with "git+ssh" instead of "git")

        Returns a tuple (<username>, <reponame>) or None if this does not seem to be a Github repo.

        Notably, the repo *must* have exactly username and reponame, nothing else and nothing
        more. E.g. `github.com/<username>/<reponame>/<something>` is *not* recognized.
        """
        if not potential_url:
            return None

        # transform 4-6 to a URL-like string, so that we can handle it together with 1-3
        if "@" in potential_url:
            split = potential_url.split("@")
            if len(split) == 2:
                potential_url = "http://" + split[1]
            else:
                # more @s ?
                return None

        # make it parsable by urlparse if it doesn't contain scheme
        if not potential_url.startswith(
            ("http://", "https://", "git://", "git+https://")
        ):
            potential_url = "http://" + potential_url

        # urlparse should handle it now
        parsed = urlparse(potential_url)

        username = None
        if ":" in parsed.netloc:
            # e.g. domain.com:foo or domain.com:1234, where foo is username, but 1234 is port number
            split = parsed.netloc.split(":")
            if split[1] and not split[1].isnumeric():
                username = split[1]

        # path starts with '/', strip it away
        path = parsed.path.lstrip("/")

        # strip trailing '.git'
        if path.endswith(".git"):
            path = path[: -len(".git")]

        split = path.split("/")
        if username and len(split) == 1:
            # path contains only reponame, we got username earlier
            return username, path
        if not username and len(split) == 2:
            # path contains username/reponame
            return split[0], split[1]

        # all other cases
        return None

    @staticmethod
    def get_username_from_git_url(url):
        """http://github.com/foo/bar.git -> foo"""
        user_repo = Git.parse_git_repo(url)
        return user_repo[0] if user_repo else None

    @staticmethod
    def get_valid_branches(
        image: str, downstream_dir: Path, branch_list: List[str]
    ) -> List[str]:
        """
        Gets the valid branches which contains `bot-cfg.yml` file.
        :param image: str: Image
        :param downstream_dir:
        :param branch_list: List of branches
        :return: list of valid branches
        """

        valid_branches = []
        for brn in branch_list:
            logger.debug("Checking 'bot-cfg.yml' in git directory in branch %r", brn)
            if Git.check_config_in_branch(downstream_dir=downstream_dir, branch=brn):
                valid_branches.append(brn)
        if not valid_branches:
            logger.info("%r does not contain any branch for syncing.", image)
            return []
        return valid_branches

    @staticmethod
    def check_config_in_branch(downstream_dir: Path, branch: str) -> bool:
        """
        Checks if the downstream branch contains 'bot-cfg.yml' file
        :param downstream_dir: Path to downstream directory where betka expects `bot-cfg.yml` file
        :param branch: Branch which betka checks
        :return: True if config file exists
                 False is config file does not exist
        """
        try:
            Git.call_git_cmd(f"checkout {branch}", msg="Change downstream branch")
        except CalledProcessError:
            logger.debug(f"It looks like {branch} does not exist yet. ")
            return False
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

    @staticmethod
    def get_reponame_from_git_url(url):
        """http://github.com/foo/bar.git -> bar"""
        user_repo = Git.parse_git_repo(url)
        return user_repo[1] if user_repo else None

    @staticmethod
    def strip_dot_git(url):
        """Strip trailing .git"""
        return url[: -len(".git")] if url.endswith(".git") else url

    @staticmethod
    def create_dot_gitconfig(user_name, user_email):
        """
        Create ~/.gitconfig file.
        :param user_name: git user name
        :param user_email: git user email
        """

        content = f"""[user]
\tname = {user_name}
\temail = {user_email}
[remote "origin"]
\tfetch = +refs/pull/*/head:refs/remotes/origin/pr/*
"""
        (Path.home() / ".gitconfig").write_text(content)
