#!/usr/bin/python3
import logging

from betka.gitlab import GitLabAPI

from betka.core import Betka
# nodejs-10 project id
PROJECT_ID = 39236632
from betka.logger import Logger

if __name__ == "__main__":
    betka = Betka(task_name="task.betka.master_sync")
    betka.set_config()
    betka.refresh_betka_yaml()
    betka.gitlab_api.set_project_id(project_id=PROJECT_ID, image="nodejs-10")
    betka.gitlab_api.get_user_from_token()
    # betka.gitlab_api.get_branches()
    # betka.gitlab_api.get_fork(count=3)
    #betka.gitlab_api.get_gitlab_fork()
    #betka.gitlab_api.get_access_request()
    #mr_id = betka.gitlab_api.check_gitlab_merge_requests(branch="rhel-8.6.0", project_id=PROJECT_ID)
    # if not mr_id:
    #     betka.gitlab_api.create_gitlab_merge_request("[betka-master-sync]")
