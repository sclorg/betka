#!/usr/bin/python3
import os


from betka.gitlab import GitLabAPI

GITLAB_TOKEN = os.environ["GITLAB_API_TOKEN"]
betka_config = {
    "gitlab_api_token": GITLAB_TOKEN,
    "downstream_master_msg": "[betka-master-sync]",
    "dist_git_repos": {
        "s2i-base": {
            "url": "https://github.com/sclorg/s2i-base-container",
            "project_id": 23,
            "project_id_fork": 24,
        },
        "postgresql": {
            "url": "https://github.com/sclorg/postgresql-container",
            "project_id": 34,
        },
        "nodejs-10": {
            "url": "https://github.com/sclorg/s2i-nodejs-container",
            "project_id": 39236632,
            "project_id_fork": 41483177,
        },
    },
}
config_json = {
    "gitlab_api_url": "https://gitlab.com",
}
gl = GitLabAPI(betka_config=betka_config, config_json=config_json)
gl.set_variables("nodejs-10")
gl.check_authentication()
gl.image = "nodejs-10"
gl.init_projects()
print(gl.get_gitlab_fork())
print(gl.get_project_forks())
print(gl.get_branches())
print(gl.get_project_mergerequests())
for brn in gl.get_branches():
    gl.check_gitlab_merge_requests(brn)
# gl.create_gitlab_merge_request("TestingMR", "MergeRequest from command line", "rhel-8.8.0")
