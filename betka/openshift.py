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

from kubernetes import config, client
from kubernetes.client.rest import ApiException

from frambo.utils import run_cmd

from betka.exception import BetkaDeployException
from betka.constants import NAME, GENERATOR_DIR


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
        self.image_url = image_url
        self.project_name = project_name
        self.image_name = image_url.split("/")[-1]
        self.image_openshift_name = self.image_name.replace(":", "-")
        self.timestamp = workdir.split("/")[-1]
        self.pod_name = (
            f"{NAME}-{self.image_openshift_name}-{self.timestamp}-deployment"
        )
        self.api_token = None
        self._kubernetes_api = None
        self.pod_manifest = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {"name": self.pod_name},
            "spec": {
                "containers": [
                    {
                        "image": self.image_url,
                        "name": self.image_openshift_name,
                        "env": [
                            {"name": "DOWNSTREAM_IMAGE_NAME", "value": downstream_name},
                            {"name": "UPSTREAM_IMAGE_NAME", "value": upstream_name},
                            {"name": "WORKDIR", "value": workdir},
                        ],
                        "volumeMounts": [
                            {"mountPath": GENERATOR_DIR, "name": "betka-generator"}
                        ],
                    }
                ],
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

    @property
    def kubernetes_api(self) -> client.CoreV1Api:
        if not self._kubernetes_api:
            self.api_token = run_cmd(["oc", "whoami", "-t"], return_output=True).strip()
            logger.debug(f"OpenShift API token: {self.api_token}")
            configuration = client.Configuration()
            configuration.api_key["authorization"] = self.api_token
            configuration.api_key_prefix["authorization"] = "Bearer"
            self._kubernetes_api = client.CoreV1Api(client.ApiClient(configuration))
        return self._kubernetes_api

    def setup_kubernetes(self):
        logger.debug("Setup kubernetes")
        config.load_incluster_config()

    def deploy_pod(self) -> bool:
        logger.info(f"Creating POD {self.pod_name} in project namespace {self.project_name}")
        resp = None
        try:
            resp = self.kubernetes_api.read_namespaced_pod(
                name=self.pod_name, namespace=self.project_name
            )
        except ApiException as e:
            logger.info(e.status)
            if e.status != 404:
                logger.error(f"Unknown error: {e!r}")
                raise BetkaDeployException
        except urllib3.exceptions.MaxRetryError as e:
            logger.info(e.reason)
            pass

        logger.debug(f"Response from read_namespaced_pod function is {resp}.")
        if not resp:
            logger.info(
                "Pod with name %r does not exist in namespace %r"
                % (self.pod_name, self.project_name)
            )
            resp = self.kubernetes_api.create_namespaced_pod(
                body=self.pod_manifest, namespace=self.project_name
            )
            count = 0

            while True:
                logger.debug("Reading POD %r information" % self.pod_name)
                resp = self.kubernetes_api.read_namespaced_pod(
                    name=self.pod_name, namespace=self.project_name
                )
                # Statuses taken from
                logger.info(f"POD status phase %r." % resp.status.phase)
                # https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#pod-phase
                if resp.status.phase == "Running":
                    logger.info("All Containers in the Pod have been created. ")
                    count = 0
                if resp.status.phase == "Failed":
                    logger.info("Container FAILED with failure.")
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
                if count > 20:
                    logger.error(
                        "Deploying POD FAILED."
                        "Either it does not start or it does not finished yet"
                        "Status is: %r" % resp.status
                    )
                    return False
        else:
            logger.error(
                f"POD with name {self.pod_name!r} "
                f"already exists in namespace {self.project_name!r}"
            )
            return True

    def deploy_image(self) -> bool:
        logger.info("Deploying image '%r' into a new POD.", self.image_name)
        if "KUBERNETES_SERVICE_HOST" in os.environ:
            self.setup_kubernetes()
            result = self.deploy_pod()
            if not result:
                logger.error("Running POD FAILED. Check betka logs for reason.")
                return False
            logger.info(
                "Running POD was successful. "
                f"Check {GENERATOR_DIR} directory for results."
            )
            self.kubernetes_api.delete_namespaced_pod(self.pod_name, self.project_name)
            logger.info(f"Pod {self.pod_name!r} was deleted")
            return True
        else:
            logger.warning("Betka IS NOT RUNNING in OpenShift.")
            return False
