#!/usr/bin/python3
from frambo.celery_app import app

import time

if __name__ == "__main__":
    # Define which tasks go to which queue
    app.conf.update(
        task_routes={
            "task.betka.master_sync": {"queue": "queue.betka.fedora"}
        }
    )
    message = {
        "topic": "org.fedoraproject.prod.github.push",
        "msg": {
            "compare": "https://github.com/sclorg/s2i-python-container/compare/27d42d5949ef...546dfadbf110",
            "repository": {
                "html_url": "https://github.com/sclorg/s2i-python-container",
                "full_name": "sclorg/s2i-python-container",
                "default_branch": "master",
                "master_branch": "master",
                "name": "s2i-python-container",
                "url": "https://github.com/sclorg/s2i-python-container",
            },
            "owner": {
                "name": "sclorg",
                "url": "https://api.github.com/users/sclorg",
                "html_url": "https://github.com/sclorg",
                "node_id": "MDEyOk9yZ2FuaXphdGlvbjkwNDc5NjA=",
                "gravatar_id": "",
                "login": "sclorg",
                "type": "Organization",
                "id": 9047960
            },
            "ref": "refs/heads/master",
            "head_commit": {
                "url": "https://github.com/sclorg/s2i-python-container/commit/546dfadbf110928dd357a55674ae7beabff8bcee",
                "tree_id": "25325362120de763581ea4c8ed782c08c742b234",
                "message": "auto-sync: master commit 897c8e39fe1df6c7bb6418d2892ccbd118d723f8",
                "removed": [],
                "id": "546dfadbf110928dd357a55674ae7beabff8bcee",
                "author": {
                    "email": "sclorg@redhat.com",
                    "name": "SCLorg Jenkins"
                },
            },
        }
    }

    result1 = app.send_task(
        name="task.betka.master_sync", kwargs={"message": message}
    )

    # Give Celery some time to pick up the message from queue and run the task
    time.sleep(5)
    print("Task1 finished? ", result1.ready())
    print("Task1 result: ", result1.result)
