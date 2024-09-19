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

"""Test Git class."""

import pytest


from subprocess import CalledProcessError
from os.path import isdir, isfile, join

from flexmock import flexmock

from betka.git import Git

from tests.conftest import get_all_branches


class TestGit(object):
    """Test Git class."""

    def test_call_git_cmd(self):
        assert Git.call_git_cmd("version").startswith("git version")

    @pytest.mark.parametrize(
        "url, ok",
        [
            ("https://github.com/sclorg/betka", True),
            # ("https://github.com/somedummy/somereallydummy", False),
        ],
    )
    def test_call_git_cmd_clone(self, tmpdir, url, ok):
        """Test Git.clone()."""
        tmpdir = str(tmpdir)
        if ok:
            assert Git.call_git_cmd(f"clone --depth=1 --single-branch {url} {tmpdir}")
            assert isdir(join(tmpdir, ".git"))
            assert isfile(join(tmpdir, "README.md"))
        else:
            with pytest.raises(CalledProcessError):
                Git.call_git_cmd(f"clone {url} {tmpdir}")

    @pytest.mark.parametrize(
        "url",
        [
            "github.com/foo/bar",
            "github.com/foo/bar.git",
            "www.github.com/foo/bar",
            "http://github.com/foo/bar",
            "http://github.com/foo/bar.git",
            "git+https://www.github.com/foo/bar",
            "git@github.com:foo/bar",
            "git@github.com:foo/bar.git",
            "git+ssh@github.com:foo/bar.git",
            "ssh://git@github.com:foo/bar.git",
            "gitlab.domain.com/foo/bar",
            "git@gitlab.domain.com:foo/bar.git",
            "https://bitbucket.org/foo/bar",
            "ssh://git@git.src.domain.com:32101/foo/bar.git",
        ],
    )
    def test_parse_gh_repo_ok(self, url):
        """Test parse_gh_repo()."""
        assert Git.parse_git_repo(url) == ("foo", "bar")
        assert Git.get_username_from_git_url(url) == "foo"
        assert Git.get_reponame_from_git_url(url) == "bar"

    @pytest.mark.parametrize(
        "url", ["something", "something@else", "http://github.com/user/repo/something"]
    )
    def test_parse_gh_repo_nok(self, url):
        """Test parse_gh_repo()."""
        assert Git.parse_git_repo(url) is None

    @pytest.mark.parametrize(
        "url, expected_result",
        [
            ("git@gitlab.domain.com:foo/bar.git", "git@gitlab.domain.com:foo/bar"),
            ("github.com/foo/bar", "github.com/foo/bar"),
        ],
    )
    def test_strip_dot_git(self, url, expected_result):
        """Test strip_dot_git()."""
        assert Git.strip_dot_git(url) == expected_result

    # def test_create_dot_gitconfig(self, tmpdir):
    #     Git.call_git_cmd(f"init {tmpdir}")
    #     user_name = "Jara Cimrman"
    #     Git.create_dot_gitconfig(user_name=user_name, user_email="mail")
    #     assert Git.call_git_cmd("config --get user.name").strip() == user_name

    @pytest.mark.parametrize(
        "all_branches, expected_result",
        [
            (["rhel-8.8", "rhel-8.8-branch", "rhel-7.7"], ["rhel-8.8"]),
            (["F34", "F35"], []),
            (["rhel-7", "rhscl38"], ["rhscl38"]),
        ],
    )
    def test_branches_to_synchronize(self, all_branches, expected_result):
        betka_config = {"synchronize_branches": ["rhscl38", "rhel7", "rhel-8.8"]}
        result_list = Git.branches_to_synchronize(betka_config=betka_config, all_branches=all_branches)
        assert result_list == expected_result

    @pytest.mark.parametrize(
        "upstream_msg, expected_msg",
        [
            ("Something message", "Something message"),
            (["Something message1", "Something message2"], ["Something message1", "Something message2"]),
            ("Something msg's", "Something msg\'s"),
            (["Something msg's 1", "Something msg's 2"], ["Something msg\'s 1", "Something msg\'s 2"]),
            ("", ""),

        ],
    )
    def test_update_msg(self, upstream_msg, expected_msg):
        result_msg = Git.update_upstream_msg(upstream_msg)
        assert result_msg == expected_msg

    def test_git_all_branches(self):
        branches_all = get_all_branches()
        flexmock(Git).should_receive("get_all_branches").and_return(branches_all)
        result_list = Git.get_valid_remote_branches()
        assert "rhel-9.5.0" in result_list
        assert "rhel-8.10.0-rhel810-sync" not in result_list
        assert "rhel-9.5.0.0" not in result_list
