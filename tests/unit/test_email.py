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

from pathlib import Path


from betka.constants import TEMPLATES
from betka.utils import text_from_template

class TestEmails:

    def setup_method(self):
        self.container = "postgresql-container"
        self.commit_sha = "123456789"
        self.downstream_name = "postgresql-12"
        self.template_dir = Path(__file__).parent.parent.parent / "files/home/templates"
    def test_create_mergerequest_message(self):
        status = "created"
        mr_number = 1
        betka_dict = {
            "status": status,
            "commit": self.commit_sha,
            "upstream_repo": f"https://github.com/sclorg/{self.container}",
            "namespace": "redhat/rhel/containers",
            "mr_number": mr_number,
            "gitlab": "https://gitlab.com",
            "image": self.downstream_name
        }

        test_message = text_from_template(
            template_dir=self.template_dir,
            template_filename="email_template",
            template_data=betka_dict
        )
        assert test_message
        assert f"Betka {status} merge request:" in test_message
        assert f"branch https://github.com/sclorg/{self.container} and synced" in test_message
        assert f"https://gitlab.com/redhat/rhel/containers/{self.downstream_name}/-/merge_requests/{mr_number}" in test_message

    def test_updated_mergerequest_message(self):
        status = "updated"
        mr_number = 2
        betka_dict = {
            "status": status,
            "commit": self.commit_sha,
            "upstream_repo": f"https://github.com/sclorg/{self.container}",
            "namespace": "redhat/rhel/containers",
            "mr_number": mr_number,
            "gitlab": "https://gitlab.com",
            "image": self.downstream_name
        }
        test_message = text_from_template(
            template_dir=self.template_dir,
            template_filename="email_template",
            template_data=betka_dict
        )
        assert test_message
        assert f"Betka {status} merge request:" in test_message
        assert f"branch https://github.com/sclorg/{self.container} and synced" in test_message
        assert f"https://gitlab.com/redhat/rhel/containers/{self.downstream_name}/-/merge_requests/{mr_number}" in test_message
