#!/bin/bash

set -ex

# for debugging purposes: iputils (ping), redis (redis-cli)
# for bots: krb5-workstation, nss_wrapper

function download_oc_client() {
  CLIENT_NAME="openshift-client-linux.tar.gz"
  OC_CLIENT_DIR="/usr/local/oc-v4/bin"
  pushd /tmp
  mkdir -p "${OC_CLIENT_DIR}"
  curl -L --insecure -o ${CLIENT_NAME} https://mirror.openshift.com/pub/openshift-v4/clients/ocp/stable-4.14/openshift-client-linux.tar.gz
  tar -xzvf ${CLIENT_NAME}
  mv oc "${OC_CLIENT_DIR}/"
  rm -f ./README ./kubectl ./${CLIENT_NAME}
  popd

}
download_oc_client

mkdir --mode=775 /var/tmp/betka-generator
mkdir -p ${HOME}/config
useradd -u 1000 -r -g 0 -d ${HOME} -s /bin/bash -c "Default Application User" ${NAME}
chown -R 1000:0 ${HOME}
chmod -R g+rwx ${HOME}
