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

from tests.conftest import betka_yaml


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

    @pytest.mark.parametrize(
        "msg_upstream_url,return_value",
        [
            ("https://github.com/sclorg/postgresql-container", {"postgresql": 34}),
            ("https://github.com/sclorg/s2i-nodejs-container", {"nodejs-10": 45}),
            ("https://github.com/sclorg/s2i-nginx-container", {"nginx": 56}),
        ],
    )
    def test_get_synced_images(self, msg_upstream_url, return_value):
        self.betka.betka_config = betka_yaml()
        self.betka.msg_upstream_url = msg_upstream_url
        dict_images = self.betka.get_synced_images()
        for image, project_id in dict_images.items():
            assert image == image in return_value
            assert project_id == return_value[image]

    @pytest.mark.parametrize(
        "msg_upstream_url,return_value",
        [
            (
                "https://github.com/sclorg/s2i-base-container",
                {"s2i-core": 12, "s2i-base": 23},
            ),
        ],
    )
    def test_double_get_synced_images(self, msg_upstream_url, return_value):
        self.betka.betka_config = betka_yaml()
        self.betka.msg_upstream_url = msg_upstream_url
        dict_images = self.betka.get_synced_images()
        assert "s2i-core" in dict_images
        assert return_value["s2i-core"] == dict_images["s2i-core"]
        assert "s2i-base" in dict_images
        assert return_value["s2i-base"] == dict_images["s2i-base"]

    @pytest.mark.parametrize(
        "msg_upstream_url,return_value",
        [
            ("https://github.com/foo/bar", None),
            ("https://github.com/sclorg/s2i-nginx-containers", None),
        ],
    )
    def test_none_get_synced_images(self, msg_upstream_url, return_value):
        self.betka.betka_config = betka_yaml()
        self.betka.msg_upstream_url = msg_upstream_url
        dict_images = self.betka.get_synced_images()
        assert not dict_images

    def test_no_project_id_get_synced_images(self):
        self.betka.betka_config = betka_yaml()
        self.betka.betka_config["dist_git_repos"]["nginx-container"].pop("project_id")
        self.betka.msg_upstream_url = "https://github.com/sclorg/s2i-nginx-container"
        dict_images = self.betka.get_synced_images()
        assert not dict_images
