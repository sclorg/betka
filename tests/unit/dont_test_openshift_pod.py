"""Test betka core class"""
import logging

from frambo.utils import run_cmd

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class TestOpenshiftPod(object):

    def setup_method(self):
        self.API_TOKEN = run_cmd(logger, ["oc", "whoami", "-t"], return_output=True)

    def _call_openshift_cmd(self, cmd, status=False):
        cmd = cmd.split(" ")
        return run_cmd(logger, cmd, return_output=True, ignore_error=status)

    def test_betka_run_pod(self):
        assert self.API_TOKEN
        logger.info(self.API_TOKEN)
        pods = self._call_openshift_cmd("oc get pods --no-headers")
        logger.debug(pods)
        assert pods
        betka_pod = [p.strip(' ') for p in pods.split() if not p.startswith("betka-1-deploy")]
        assert betka_pod
        list_dir = self._call_openshift_cmd("oc exec %s "
                                            "ls /tmp/betka-generator/results" % betka_pod[0],
                                            status=True)
        expected_files = ["Testing1.txt","Testing2.txt","Testing3.txt","Testing4.txt","Testing5.txt"]
        assert set(list_dir.split()) == set(expected_files)
