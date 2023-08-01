#!/bin/bash

set -x
if podman ps -a --noheading | grep redis ; then
  echo "redis is already running. Stopping and removing it."
  podman stop redis
  podman rm redis
fi
podman run -d --rm -p 6379:6379 --name redis docker.io/centos/redis-32-centos7

if podman ps betka ; then
  podman stop betka
fi

if [ -z "$GITHUB_TOKEN" ]; then
  echo "Define environment variable GITHUB_TOKEN."
  exit 1
fi

if [ -z "$GITLAB_API_TOKEN" ]; then
  echo "Define environment variable GITLAB_API_TOKEN."
  exit 1
fi

podman run --rm --net=host -v ./examples:/home/betka/examples -v ./logs:/tmp/bots/ \
    -e DEPLOYMENT=prod -e GITHUB_API_TOKEN=${GITHUB_API_TOKEN} -e GITLAB_API_TOKEN=${GITLAB_API_TOKEN} \
    -e SLACK_WEBHOOK_URL=${SLACK_WEBHOOK_URL} \
    -e REDIS_SERVICE_HOST=localhost --name betka \
    quay.io/rhscl/betka
