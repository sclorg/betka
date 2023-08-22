#!/usr/bin/env python3

import json
import logging

import requests
import sys
import yaml

from os import getenv
from pathlib import Path

from betka.emails import BetkaEmails

DEPLOYMENT = getenv("DEPLOYMENT")
if not DEPLOYMENT:
    raise ValueError("Please set DEPLOYMENT environment variable.")

logger = logging.getLogger(__name__)

def pretty_dict(report_dict):
    result = json.dumps(report_dict, sort_keys=True, indent=4)
    result = result.replace("\\n", "\n")
    return result


def fetch_config(config_file_url):
    bots_config = ""
    logger.info(f"Pulling config file: {config_file_url}")
    r = requests.get(config_file_url, verify=False)
    r.raise_for_status()
    if r.status_code == 200:
        bots_config = r.text
        logger.debug("Bot configuration fetched")
    else:
        logger.warning(
            f"Config file not found in url: {config_file_url}, "
            "using default configuration."
        )
        BetkaEmails.send_email(
            text=f"Downloading {config_file_url} failed with reason {r.status_code} and {r.reason}.",
            receivers=["phracek@redhat.com"],
            subject=f"[betka-run] Downloading {config_file_url} failed.",
        )
        return {}
    config = load_configuration(conf_str=bots_config)
    if "betka" in config:
        return config.get("betka")
    if "upstream-to-downstream" in config:
        return config.get("upstream-to-downstream")
    return {}


def load_configuration(conf_path=None, conf_str=None):

    if conf_str and conf_path:
        raise AttributeError(
            "Provided both forms of configuration."
            "Use only conf_path or only conf_str"
        )

    if not (conf_str or conf_path):
        # none provided, return default config
        return {}

    if conf_path:
        if not Path(conf_path).is_file():
            raise AttributeError(f"Configuration file not found: {conf_path}")
        conf_str = Path(conf_path).read_text()

    # Some people keep putting tabs at the end of lines
    conf_str = conf_str.replace("\t\n", "\n")

    repo_conf = yaml.safe_load(conf_str)

    repo_conf.pop("global", None)

    logger.debug(f"Resulting bots configuration: {pretty_dict(repo_conf)}")
    return repo_conf


if __name__ == "__main__":
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    if len(sys.argv) > 1:
        conf = load_configuration(sys.argv[1])
    else:
        conf = load_configuration()
