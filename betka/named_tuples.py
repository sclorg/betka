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

from collections import namedtuple


ProjectMRs = namedtuple(
    "ProjectMRs", ["iid", "project_id", "target_branch", "title", "username"]
)
ProjectBranches = namedtuple("ProjectBranches", ["name", "web_url", "protected"])

CurrentUser = namedtuple("CurrentUser", ["id", "username"])
ProjectMR = namedtuple(
    "ProjectMR",
    [
        "iid",
        "title",
        "description",
        "target_branch",
        "author",
        "source_project_id",
        "target_project_id",
        "web_url",
    ],
)
ProjectFork = namedtuple(
    "ProjectFork",
    [
        "id",
        "name",
        "ssh_url_to_repo",
        "username",
        "forked_from_id",
        "forked_ssh_url_to_repo",
    ],
)
ForkProtectedBranches = namedtuple("ProtectedBranches", ["name"])
ProjectInfo = namedtuple("ProjectInfo", ["id", "name", "ssh_url_to_repo", "web_url"])
