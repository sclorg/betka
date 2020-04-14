#!/bin/bash

set -x

RESULT_DIR="${GENERATOR_HOME}/results"
mkdir -p ${RESULT_DIR}
for i in `seq 1 5`; do
    echo "Testing$i" > "${RESULT_DIR}/Testing${i}.txt"
done
