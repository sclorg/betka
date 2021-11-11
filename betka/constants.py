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


GIT_PATH = "/{u}/{n}/{r}/git/"
PAGURE_NEW_PR = "/{u}/{n}/{r}/pull-request/new"
NAME = "betka"
HOME = "/home/{n}".format(n=NAME)
TEMPLATES = "{h}/templates".format(h=HOME)
COMMIT_REPO = "UpstreamRepository: {repo}"
COMMIT_MASTER_MSG = (
    "\n\nUpstreamCommitID: {hash}\n"
    "UpstreamCommitLink: {repo}/commit/{hash}\n" + COMMIT_REPO
)
DOWNSTREAM_CONFIG_FILE = "bot-cfg.yml"
GENERATOR_DIR = "/tmp/betka-generator"
SYNCHRONIZE_BRANCHES = "synchronize_branches"
# Sync betka.yaml interval set to 5 hours
SYNC_INTERVAL = 60 * 60 * 5

RETRY_CREATE_POD = 10
