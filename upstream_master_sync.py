#!/usr/bin/python3
from frambo.celery_app import app

import time

if __name__ == "__main__":
    # Define which tasks go to which queue
    app.conf.update(
        task_routes={
            "task.betka.master_sync": {"queue": "queue.betka-fedora"}
        }
    )
    message = {
        "msg": {
            "repository": {
                "html_url": "https://github.com/sclorg/s2i-python-container",
                "full_name": "sclorg/s2i-python-container",
            },
            "ref": "refs/heads/master",
            "head_commit": {
                "id": "f65cb365f80b70e6219390f912492ed2b40132f3",
                "message": "Merge pull request #372 from sclorg/micropipenv\n\nVery first try to add micropipenv to the images",
                "author": {"name": "phracek"},
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
