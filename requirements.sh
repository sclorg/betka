#!/bin/bash

set -ex

# for debugging purposes: iputils (ping), redis (redis-cli)
# for bots: krb5-workstation, nss_wrapper

dnf install -y --setopt=tsflags=nodocs distgen nss_wrapper krb5-devel krb5-workstation origin-clients openssh-clients \
            gcc rpm-devel openssl-devel libxml2-devel redhat-rpm-config make git \
            iputils redis krb5-workstation nss_wrapper \
            python3-devel python3-pip python3-gitlab
dnf clean all

mkdir --mode=775 /tmp/betka-generator
mkdir -p ${HOME}/config
useradd -u 1000 -r -g 0 -d ${HOME} -s /bin/bash -c "Default Application User" ${NAME}
chown -R 1000:0 ${HOME}
chmod -R g+rwx ${HOME}
