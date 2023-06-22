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
from tests.conftest import config_json


class TestBetkaCore(object):
    def setup_method(self):
        os.environ["GITHUB_API_TOKEN"] = "aklsdjfh19p3845yrp"
        os.environ["GITLAB_API_TOKEN"] = "testing"
        os.environ["GITLAB_USER"] = "testymctestface"
        os.environ["SLACK_WEBHOOK_URL"] = "https://dummy.url"
        self.betka = Betka()
        self.betka.config_json = config_json()

    @pytest.fixture()
    def json_init(self):
        return {
            "msg": {
                "repository": {
                    "html_url": "https://github.com/sclorg/s2i-base-container"
                },
                "comment": "[citest]",
                "issue": {
                    "number": 75,
                    "title": "Update 10.2 fedora dockerfile for f28, and run rpm-file-permissions",
                },
            }
        }

    @pytest.fixture()
    def json_missing_repository(self):
        return {"msg": {"issue": {"number": 75}}}

    @pytest.fixture()
    def json_missing_pullrequest(self):
        return {
            "msg": {
                "repository": {
                    "html_url": "https://github.com/sclorg/s2i-base-container"
                },
                "issue": {"number": 75},
            }
        }

    @pytest.fixture()
    def json_missing_issue(self):
        return {
            "msg": {
                "repository": {
                    "html_url": "https://github.com/sclorg/s2i-base-container"
                }
            }
        }

    @pytest.fixture()
    def json_empty_head_commit(self):
        return {"msg": {}}

    @pytest.fixture()
    def json_missing_head_commit(self):
        return {"msg": {"head_commit": None}}

    def test_update_config(self):
        self.betka.set_config()
        assert self.betka.betka_config.get("github_api_token") == "aklsdjfh19p3845yrp"
        assert self.betka.betka_config.get("gitlab_api_token") == "testing"
        assert self.betka.betka_config.get("gitlab_user") == "testymctestface"
        assert self.betka.betka_config.get("slack_webhook_url") == "https://dummy.url"

    def test_wrong_fedmsg_info(self, json_init):
        json_init["topic"] = "org.fedoraproject.prod.github.testing"
        assert not self.betka.get_master_fedmsg_info(json_init)

    def test_miss_repo_fedmsg_info(self, json_missing_repository):
        assert not self.betka.get_master_fedmsg_info(json_missing_repository)

    def test_pullrequest_fedmsg_info(self, json_missing_pullrequest):
        assert not self.betka.get_master_fedmsg_info(json_missing_pullrequest)

    def test_missing_issue_fedmsg_info(self, json_missing_issue):
        with pytest.raises(AttributeError):
            self.betka.get_pr_fedmsg_info(json_missing_issue)

    def test_empty_head_commit_fedmsg_info(self, json_empty_head_commit):
        assert not self.betka.get_master_fedmsg_info(json_empty_head_commit)

    def test_miss_head_commit_fedmsg_info(self, json_missing_head_commit):
        assert not self.betka.get_master_fedmsg_info(json_missing_head_commit)
