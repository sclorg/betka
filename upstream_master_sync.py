#!/usr/bin/python3
from frambo.celery_app import app

import time

if __name__ == "__main__":
    # Define which tasks go to which queue
    app.conf.update(
        task_routes={
            "task.betka.upstream2downstream.master_sync": {"queue": "queue.betka"}
        }
    )
    message = {
        "msg": {
            "repository": {
                "html_url": "https://github.com/sclorg/s2i-base-container",
                "full_name": "sclorg/s2i-base-container",
            },
            "ref": "refs/heads/master",
            "head_commit": {
                "id": "12988a701f8296e44eaf2e796457f8cb2aabd096",
                "message": "Update of the common submodule",
                "author": {"name": "phracek"},
            },
        }
    }

    result1 = app.send_task(
        name="task.betka.upstream2downstream.master_sync", kwargs={"message": message}
    )

    # Give Celery some time to pick up the message from queue and run the task
    time.sleep(5)
    print("Task1 finished? ", result1.ready())
    print("Task1 result: ", result1.result)
