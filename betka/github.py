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

import logging
import requests

from typing import Dict

from betka.exception import BetkaException
from betka.urls import GIT_HUB_API_4

logger = logging.getLogger(__name__)


class GitHubAPI(object):
    def __init__(self, image: str, headers: str, repo_name: str, user: str):
        self.image = image
        self.headers = headers
        self.repo_name = repo_name
        self.user = user

    @staticmethod
    def _detect_api_errors(response):
        """Looks for the errors in API response"""
        msg = "\n".join((err["message"] for err in response.get("errors", [])))
        if msg:
            raise BetkaException(msg)

    def send_query(self, query: str) -> requests.Response:
        """ Sends the query to GitHub v4 API and returns the response """
        return requests.post(
            url=GIT_HUB_API_4, json={"query": query}, headers=self.headers
        )

    def query_repository(self, query: str) -> requests.Response:
        """ Query GitHub repository """
        repo_query = (
            f'query {{repository(owner: "{self.user}", '
            f'name: "{self.repo_name}") {{{query}}}}} '
        )
        return self.send_query(repo_query)

    def get_pull_requests(self, state: str) -> Dict:
        """
        Gets all pull request from upstream.
        :return: pull request dictionary
        Format of pr_dict is:
        {title: "TITLE",
         number: "Pull request number",
         commit: "Commit hash" }

        """
        logger.info("Function get_pull_requests for image {i}".format(i=self.image))
        query = """pullRequests(states: [{s}], first: 10) {{
            edges {{
              node {{
                title
                number
                commits(first: 1) {{
                  nodes {{
                    commit {{
                      oid
                    }}
                  }}
                }}
              }}
            }}
        }}
                    """.format(
            s=state
        )
        r_com = self.query_repository(query).json()
        self._detect_api_errors(r_com)
        pr_dict: Dict = {}
        try:
            edges = r_com["data"]["repository"]["pullRequests"]["edges"]
            if not edges:
                logger.debug("There is no github PR for image %r", self.image)
            for nodes in edges:
                for key, val in nodes.items():
                    try:
                        commits = val["commits"]["nodes"][0]
                        commit = commits["commit"]["oid"]
                    except KeyError:
                        commit = ""
                    pr_dict = {
                        "title": val["title"],
                        "number": val["number"],
                        "commit": commit,
                    }
            logger.debug(pr_dict)
        except KeyError:
            logger.debug("There is no github PR for image %r", self.image)
        except IndexError:
            logger.debug("There is no github PR for image %r", self.image)
        return pr_dict

    def check_upstream_pr(self, number: int) -> str:
        """
        Gets the latest comment for corresponding PR.
        :param number: number of PR to check
        :return: True ... expected comment detected
                 False ... either no comment or the latest comment does not equal
        """
        # https://github.com/user-cont/release-bot/blob/master/release_bot/github.py#L46
        # Gets all comments per PR and store datetime and text message for analyzation
        query = """pullRequest(number: {n}) {{
          state
        }}
                    """.format(
            n=number
        )
        r_com = self.query_repository(query).json()
        self._detect_api_errors(r_com)
        # check for empty node
        state = r_com["data"]["repository"]["pullRequest"]["state"]
        if not state:
            logger.debug("There is no state defined for PR {d} yet.".format(d=number))
            return ""
        return state
