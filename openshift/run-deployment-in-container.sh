#!/bin/bash -e

here=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
IMAGE_NAME="quay.io/rhscl/betka-deployment"

set -x

if [ -z "${DEPLOYMENT}" ]; then
    echo "DEPLOYMENT has to be defined (to one of prod/stage/dev/test)"
    exit 1
fi

docker run -ti \
           --rm \
           -e DEPLOYMENT=${DEPLOYMENT} \
           ${IMAGE_NAME}
