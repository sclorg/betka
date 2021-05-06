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

from betka.git import Git
from tests.conftest import betka_yaml


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
    "all_branches,expected",
    [
        (["fc29", "fc27"], []),
        (["fc30", "fc29"], ["fc30"]),
        (["fc30", "fc31", "fc29"], ["fc30", "fc31"]),
        (["fc30", "fc31", "fc32"], ["fc30", "fc31", "fc32"]),
        (["fc32", "master"], ["fc32"]),
    ],
)
def test_is_branch_synced(all_branches, expected):
    betka_config = betka_yaml()
    assert (
        Git.branches_to_synchronize(
            betka_config=betka_config, all_branches=all_branches
        )
        == expected
    )
