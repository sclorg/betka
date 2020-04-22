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


PAGURE_HOST = "https://pkgs.fedoraproject.org"
PAGURE_HOST_HTTPS = "https://src.fedoraproject.org"
API_URL = "/api/0"
PR_FORK = API_URL + "/fork"
PR_API = API_URL + "/{namespace}/{repo}/pull-request/new"
GET_PR_COMMENT = "/{namespace}/{repo}/pull-request/{id}/comment"
GET_ALL_PR = "/{namespace}/{repo}/pull-requests"
GET_USER_URL = "https://src.fedoraproject.org" + API_URL + "/-/whoami"
GIT_HUB_API_4 = "https://api.github.com/graphql"
NAMESPACE_CONTAINERS = "container"
PULL_REQUEST_URL = "ssh://{username}@pkgs.fedoraproject.org"