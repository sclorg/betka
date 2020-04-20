from frambo.celery_app import app

from betka.core import Betka


@app.task(name="task.betka.master_sync")
def master_sync(message):
    betka = Betka(task_name="task.betka.master_sync")
    if betka.get_master_fedmsg_info(message) and betka.prepare():
        betka.run_sync()


@app.task(name="task.betka.pr_sync")
def pr_sync(message):
    betka = Betka(task_name="task.betka.pr_sync")
    if betka.get_pr_fedmsg_info(message) and betka.prepare():
        betka.run_sync()
