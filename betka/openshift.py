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
import os
import time
import urllib3

from kubernetes.client import (
    CoreV1Api,
    Configuration,
    ApiClient,
    V1Pod,
    V1DeleteOptions,
)
from kubernetes.config import load_incluster_config
from kubernetes.client.rest import ApiException

from frambo.utils import run_cmd

from betka.exception import BetkaDeployException
from betka.constants import NAME, GENERATOR_DIR, RETRY_CREATE_POD


logger = logging.getLogger(__name__)


class OpenshiftDeployer(object):
    def __init__(
        self,
        upstream_name: str,
        downstream_name: str,
        workdir: str,
        image_url: str,
        project_name: str,
    ):
        self.image_url: str = image_url
        self.project_name: str = project_name
        self.image_name: str = image_url.split("/")[-1]
        self.image_openshift_name: str = self.image_name.replace(":", "-")
        self.timestamp: str = workdir.split("/")[-1]
        self.workdir = workdir
        self.pod_name: str = (
            f"{NAME}-{self.image_openshift_name}-{self.timestamp}-deployment"
        )
        self.api = self.kubernetes_api()
        self.upstream_name: str = upstream_name
        self.downstream_name: str = downstream_name

    @staticmethod
    def kubernetes_api() -> CoreV1Api:
        configuration = Configuration()
        load_incluster_config()
        if not configuration.api_key:
            raise BetkaDeployException("No api_key, can't access any cluster.\n")
        return CoreV1Api(ApiClient(configuration=configuration))

    def create_manifest_file(self) -> dict:
        env_vars = [
            {"name": "DOWNSTREAM_IMAGE_NAME", "value": self.downstream_name},
            {"name": "UPSTREAM_IMAGE_NAME", "value": self.upstream_name},
            {"name": "WORKDIR", "value": self.workdir},
        ]
        container = {
            "image": self.image_url,
            "name": self.image_openshift_name,
            "env": env_vars,
            "volumeMounts": [
                {
                    "mountPath": GENERATOR_DIR,
                    "name": "betka-generator"
                }
            ]
        }

        pod_manifest = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {"name": self.pod_name},
            "spec": {
                "containers": [container],
                "restartPolicy": "Never",
                "serviceAccountName": "betka",
                "volumes": [
                    {
                        "name": "betka-generator",
                        "persistentVolumeClaim": {"claimName": "claim.betka"},
                    }
                ],
            },
        }
        return pod_manifest

    def get_pod(self) -> V1Pod:
        logger.debug(f"Check if pod is already running")
        return self.api.read_namespaced_pod(name=self.pod_name, namespace=self.project_name)

    def is_pod_already_deployed(self) -> bool:
        """
        Check if pod is already deployed
        """
        try:
            self.get_pod()
            return True
        except ApiException as e:
            logger.info(e.status)
            if e.status == 403:
                logger.error("betka is not allowed to get info about the pod.")
                logger.info("exception = %r", e)
                raise BetkaDeployException
            if e.status != 404:
                logger.error(f"Unknown error: {e!r}")
                logger.info(f"Something is wrong with pod: {e}")
                raise BetkaDeployException

    def delete_pod(self):
        """
        Delete the cwt pod.
        :return: response from the API server
        """
        try:
            self.api.delete_namespaced_pod(
                self.pod_name, self.project_name, body=V1DeleteOptions()
            )
        except ApiException as e:
            logger.debug(e)
            if e.status != 404:
                raise

    def create_pod(self, pod_manifest) -> dict:
        """
        Create pod in a namespace
        :return: response from the API server
        """
        # if we hit timebound quota, let's try 5 times with expo backoff
        for idx in range(1, RETRY_CREATE_POD):
            try:
                logger.debug(f"Creating sandbox pod via kubernetes API, try {idx}")
                return self.api.create_namespaced_pod(
                    body=pod_manifest, namespace=self.project_name
                )
            except ApiException as ex:
                logger.info(f"Unable to create the pod: {ex}")
                # reproducer for this is to set memory quota for your cluster:
                # https://docs.openshift.com/online/pro/dev_guide/compute_resources.html#dev-memory-requests
                if ex.status == "403":  # forbidden
                    sleep_time = 3 ** idx
                    logger.debug(f"Trying again in {sleep_time}s")
                    time.sleep(sleep_time)
                else:
                    raise
        raise BetkaDeployException("Unable to schedule the betka-cwt pod.")

    def get_pod_logs(self) -> str:
        """ provide logs from the pod """
        return self.api.read_namespaced_pod_log(
            name=self.pod_name, namespace=self.project_name
        )

    def deploy_pod(self) -> bool:
        logger.info(f"Deploying POD {self.pod_name} in project namespace {self.project_name}")
        if self.is_pod_already_deployed():
            self.delete_pod()

        pod_manifest = self.create_manifest_file()
        logger.debug(f"Manifest file: {pod_manifest}")
        self.create_pod(pod_manifest=pod_manifest)

        count = 0
        # Wait for pod to start
        logger.debug(f"Pod {self.pod_name}")
        while True:
            logger.debug("Reading POD %r information" % self.pod_name)
            resp = self.get_pod()
            # Statuses taken from
            logger.info(f"POD status phase %r." % resp.status.phase)
            # https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#pod-phase
            if resp.status.phase == "Running":
                logger.info("All Containers in the Pod have been created. ")
                count = 0
            if resp.status.phase == "Failed":
                logger.info("Container FAILED with failure.")
                logger.info(self.get_pod_logs())
                return False
            if resp.status.phase == "Succeeded":
                logger.info("All Containers in the Pod have terminated in success.")
                return True
            if resp.status.phase == "Pending":
                logger.info("Waiting for container to be in state 'Running'.")
            # Wait for a second before another POD check
            time.sleep(6)
            count += 1
            # If POD does not start during two minutes, then it probably failed.
            if count > 100:
                logger.error(
                    "Deploying POD FAILED."
                    "Either it does not start or it does not finished yet during 600s."
                    "Status is: %r" % resp.status
                )
                logger.info(self.get_pod_logs())
                return False

    def deploy_image(self) -> bool:
        logger.info("Deploying image '%r' into a new POD.", self.image_name)
        if "KUBERNETES_SERVICE_HOST" in os.environ:
            result = self.deploy_pod()
            if not result:
                logger.error("Running POD FAILED. Check betka logs for reason.")
                return False
            logger.info(
                "Running POD was successful. "
                f"Check {GENERATOR_DIR} directory for results."
            )
            self.delete_pod()
            logger.info(f"Pod {self.pod_name!r} was deleted")
            return True
        else:
            logger.warning("Betka IS NOT RUNNING in OpenShift.")
            return False
