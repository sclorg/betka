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

import os
import pytest

from betka.core import Betka


class TestBetkaCore(object):
    def setup_method(self):
        os.environ["GITHUB_API_TOKEN"] = "aklsdjfh19p3845yrp"
        os.environ["PAGURE_API_TOKEN"] = "testing"
        os.environ["GITLAB_USER"] = "testymctestface"
        self.betka = Betka()

    @pytest.mark.parametrize(
        "betka_json,bot_json,return_value",
        [
            (
                {"api_url": "https://src.fedoraproject.org/api/0"},
                {"enabled": True},
                None,
            ),
            (
                {
                    "api_url": "https://src.fedoraproject.org/api/0",
                    "generator_url": "quay.io/foo/bar",
                },
                {"enabled": True},
                "quay.io/foo/bar",
            ),
            (
                {"api_url": "https://src.fedoraproject.org/api/0"},
                {"enabled": True, "image_url": "quay.io/betka/generator"},
                "quay.io/betka/generator",
            ),
        ],
    )
    def test_image_url(self, betka_json, bot_json, return_value):
        self.betka.betka_config = betka_json
        self.betka.config = bot_json
        assert self.betka._get_image_url() == return_value
