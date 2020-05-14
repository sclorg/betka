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


"""Test betka core class"""

import pytest

from flexmock import flexmock

from betka.pagure import PagureAPI
from betka.constants import SYNCHRONIZE_BRANCHES
from tests.conftest import no_pullrequest, one_pullrequest


class TestBetkaPagure(object):
    def betka_config(self):
        return {
            SYNCHRONIZE_BRANCHES: ["f3", "master"],
            "version": "1",
            "dist_git_repos": {
                "s2i-core": ["https://github.com/sclorg/s2i-base-container"]
            },
            "pagure_user": "foo",
        }

    def setup_method(self):
        self.pa = PagureAPI(config=self.betka_config())
        self.pa.image = "foobar"

    @pytest.mark.parametrize(
        "branches,expected",
        [
            (["f29", "f27"], []),
            (
                    ["f30", "f29"],
                    ["f30"],
            ),
            (["f30", "f31", "f29"], ["f30", "f31"]),
            (
                    ["f30", "f31", "f32"],
                    ["f30", "f31", "f32"],
            ),
            (
                    ["f32", "master"],
                    ["f32", "master"],
            ),
        ],
    )
    def test_is_branch_synced(self, branches, expected):
        assert self.pa.branches_to_synchronize(branches) == expected

    @pytest.mark.parametrize(
        "branches,status_code,expected",
        [
            (
                    ["f30", "master", "private"],
                    200,
                    ["f30", "master", "private"]
            ),
            (
                    ["f30", "master", "private"],
                    400,
                    []
            )
        ]
    )
    def test_get_branches(self, branches, status_code, expected):
        flexmock(
            PagureAPI,
            get_status_and_dict_from_request=(status_code, branches)
        )
        assert self.pa._get_branches() == expected

    @pytest.mark.parametrize(
        "json_file,msg,check_user,return_code",
        [
            (
                no_pullrequest(), "", False,
                None,
            ),
            (
                one_pullrequest(), "abc", False,
                None,
            ),
            (
                one_pullrequest(), "Update from the upstream", False,
                5,
            ),
            (
                one_pullrequest(), "Update from the upstream", True,
                5,
            )
        ]
    )
    def test_downstream_pull_requests(self, json_file, msg, check_user, return_code):
        flexmock(self.pa)\
            .should_receive("get_status_and_dict_from_request")\
            .with_args(url="https://src.fedoraproject.org/api/0/container/foobar/pull-requests",
                       msg="requests")\
            .and_return(json_file["requests"])
        assert self.pa.check_downstream_pull_requests(
            msg_to_check=msg,
            check_user=check_user
        ) == return_code
