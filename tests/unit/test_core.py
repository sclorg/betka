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

from flexmock import flexmock

from betka.core import Betka
from betka.utils import SlackNotifications
from betka.named_tuples import ProjectMR

from tests.conftest import betka_yaml

class TestBetkaDevelMode(object):
    def setup_method(self):
        os.environ["GITHUB_API_TOKEN"] = "aklsdjfh19p3845yrp"
        os.environ["PAGURE_API_TOKEN"] = "testing"
        os.environ["GITLAB_USER"] = "testymctestface"
        self.betka = Betka()
        self.betka.config_json = {}

    def test_is_devel_mode_set(self):
        os.environ["DEVEL_MODE"] = "true"
        self.betka.set_environment_variables()
        assert self.betka.betka_config["devel_mode"] == "true"
        assert bool(self.betka.betka_config.get("devel_mode")) == True

    def test_devel_mode_set_false(self):
        os.environ["DEVEL_MODE"] = "false"
        self.betka.set_environment_variables()
        assert self.betka.betka_config["devel_mode"] == "false"

    def test_devel_mode_not_set(self):
        self.betka.set_environment_variables()
        assert self.betka.betka_config["devel_mode"] == "false"


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
            ("https://github.com/sclorg/postgresql-container", {"postgresql": "redhat/rhel/containers/postgresql-15"}),
            ("https://github.com/sclorg/s2i-nodejs-container", {"nodejs-10": "redhat/rhel/containers/nodejs-10"}),
            ("https://github.com/sclorg/s2i-nginx-container", {"nginx": "redhat/rhel/containers/nginx-122"}),
        ],
    )
    def test_get_synced_images(self, msg_upstream_url, return_value):
        self.betka.betka_config = betka_yaml()
        self.betka.msg_upstream_url = msg_upstream_url
        dict_images = self.betka.get_synced_images()
        for image, values in dict_images.items():
            assert image == image in return_value

    @pytest.mark.parametrize(
        "status,return_value",
        [
            ("True", True),
            ("true", True),
            ("False", False),
            ("false", False),
        ],
    )
    def test_is_fork_enabled(self, status, return_value):
        self.betka.betka_config["use_gitlab_forks"] = status
        assert self.betka.is_fork_enabled() == return_value

    @pytest.mark.parametrize(
        "msg_upstream_url,return_value",
        [
            (
                "https://github.com/sclorg/s2i-base-container",
                {
                    "s2i-core": {
                        "url": "https://github.com/sclorg/s2i-base-container",
                    },
                    "s2i-base": {
                        "url": "https://github.com/sclorg/s2i-base-container",
                    },
                },
            ),
        ],
    )
    def test_double_get_synced_images(self, msg_upstream_url, return_value):
        self.betka.betka_config = betka_yaml()
        self.betka.msg_upstream_url = msg_upstream_url
        dict_images = self.betka.get_synced_images()
        assert "s2i-core" in dict_images
        assert (
            return_value["s2i-core"]
            == dict_images["s2i-core"]
        )
        assert "s2i-base" in dict_images

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

    def test_send_notification_empty_dict(self):
        self.betka.betka_config = betka_yaml()
        assert not self.betka.send_result_email({})

    def test_send_webhook_not_webhook(self):
        self.betka.betka_config = betka_yaml()
        assert self.betka.slack_notification() is False

    def test_send_webhook_and_webhook_empty(self):
        self.betka.betka_config = betka_yaml()
        self.betka.betka_config["slack_webhook_url"] = ""
        assert self.betka.slack_notification() is False

    def test_send_webhook(self):
        self.betka.betka_config = betka_yaml()
        self.betka.betka_config["slack_webhook_url"] = "https://foobar/hook"
        self.betka.betka_schema = dict()
        self.betka.betka_schema["merge_request_dict"] = ProjectMR(
            iid=1,
            title="asd",
            description="fassdf",
            target_branch="rhel",
            author="phracek",
            source_project_id=1,
            target_project_id=2,
            web_url="https://gooo/bar/1",
        )
        flexmock(SlackNotifications).should_receive("send_webhook_notification").once()
        assert self.betka.slack_notification()
