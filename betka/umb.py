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


from typing import Dict, Any


class UMBSender(object):
    @staticmethod
    def send_umb_message_in_progress(artifact: Dict, url: str = None):
        UMBSender._send_umb_message(artifact, "in-progress")
        pass

    @staticmethod
    def send_umb_message_complete(artifact: Dict, results: Dict):
        UMBSender._send_umb_message(artifact, "complete")
        pass

    @staticmethod
    def send_umb_message_error(artifact: Dict, error_message, message, url: str = None):
        UMBSender._send_umb_message(artifact, "error")
        pass

    @staticmethod
    def send_umb_message_skip(
        artifact: Dict, reason: str, message: str, url: str = None
    ):
        UMBSender._send_umb_message(artifact, "skip")
        pass

    @staticmethod
    def _send_umb_message(umb_msg: Dict, topic_suffix: str = None) -> Any:
        pass
