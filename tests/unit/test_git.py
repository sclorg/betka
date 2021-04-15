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


"""Test betka.git class"""

import pytest

from flexmock import flexmock

from frambo.git import Git as FramboGit

from betka.git import Git


@pytest.mark.parametrize(
    "config,commit_msg",
    [
        ({"jira_ticket": "RHELPLAIN9876543"}, ""),
        ({"jira_ticket": "1897893"}, "Related: rhbz#1897893"),
        ({"jira_ticket": "rhbz123456"}, ""),
        ({"jira_ticket": "RHELPLAN-1237896"}, "Related: RHELPLAN-1237896"),
        ({"jira_ticket": "RHELPLAN123456"}, ""),
        ({"jira1_ticket": "RHELPLAN123456"}, ""),
        ({}, ""),
    ],
)
def test_jira_msg(config, commit_msg):
    assert Git.get_msg_from_jira_ticket(config) == commit_msg


@pytest.mark.parametrize(
    "git_output,branch,return_code",
    [
        (
            [
                "* master", "remotes/origin/HEAD -> origin/master", "remotes/origin/master",
                "remotes/origin/rhel-8.2.0", "remotes/upstream/master", "remotes/upstream/pr/1",
                "remotes/upstream/rhel-8.2.0", "remotes/upstream/rhel-8.5.0"
            ],
            "rhel-8.2.0",
            True,
        ),
        (
            [
                "* master", "remotes/origin/HEAD -> origin/master", "remotes/origin/master",
                "remotes/origin/rhel-8.2.0", "remotes/upstream/master", "remotes/upstream/pr/1",
                "remotes/upstream/rhel-8.2.0", "remotes/upstream/rhel-8.5.0"
            ],
            "rhel-8.5.0",
            False,
        ),
        (
            [
                "* master", "remotes/origin/HEAD -> origin/master", "remotes/origin/master",
                "remotes/origin/rhel-8.2.0", "remotes/upstream/master", "remotes/upstream/pr/1",
                "remotes/upstream/rhel-8.2.0", "remotes/upstream/rhel-8.5.0"
            ],
            "rhel-8.4.0",
            False,
        ),
    ]
)
def test_is_branch_local(git_output, branch, return_code):
    flexmock(Git).should_receive("get_all_branches").and_return(git_output)
    assert Git.is_branch_local(branch=branch) == return_code
