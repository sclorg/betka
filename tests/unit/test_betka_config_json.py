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

from betka.core import Betka


def config_json_missing_ocp_project_name():
    return {
        "api_url": "https://src.fedoraproject.org/api/0",
        "get_all_pr": "https://src.fedoraproject.org/api/0/{namespace}/{repo}/pull-requests",
        "git_url_repo": "https://src.fedoraproject.org/api/0/fork/{user}/{namespace}/{repo}/git/",
        "namespace_containers": "container",
        "github_api_token": "aklsdjfh19p3845yrp",
        "pagure_user": "testymctestface",
        "pagure_api_token": "testing",
    }


def config_json_missing_pagure_api_token():
    return {
        "api_url": "https://src.fedoraproject.org/api/0",
        "get_all_pr": "https://src.fedoraproject.org/api/0/{namespace}/{repo}/pull-requests",
        "git_url_repo": "https://src.fedoraproject.org/api/0/fork/{user}/{namespace}/{repo}/git/",
        "namespace_containers": "container",
        "github_api_token": "aklsdjfh19p3845yrp",
        "pagure_user": "testymctestface",
    }


def config_json_missing_github_api_token():
    return {
        "api_url": "https://src.fedoraproject.org/api/0",
        "get_all_pr": "https://src.fedoraproject.org/api/0/{namespace}/{repo}/pull-requests",
        "git_url_repo": "https://src.fedoraproject.org/api/0/fork/{user}/{namespace}/{repo}/git/",
        "namespace_containers": "container",
        "github_api_token": "aklsdjfh19p3845yrp",
        "pagure_user": "testymctestface",
    }


class TestBetkaCore(object):
    def setup_method(self):
        self.betka = Betka()

    @pytest.mark.parametrize(
        "config_json",
        [
            config_json_missing_ocp_project_name(),
            config_json_missing_pagure_api_token(),
            config_json_missing_github_api_token(),
        ]
    )
    def test_betka_config_keyerror(self, config_json):
        self.betka.config_json = config_json
        with pytest.raises(KeyError):
            self.betka.set_config()
