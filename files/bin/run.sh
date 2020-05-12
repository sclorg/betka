#!/bin/bash

set -x

# Generate passwd file based on current id
function generate_passwd_file() {
    export USER_ID=$(id -u)
    export GROUP_ID=$(id -g)
    grep -v ^betka /etc/passwd > "$HOME/passwd"
    echo "betka:x:${USER_ID}:${GROUP_ID}:Sync bot from upstream to downstream:${HOME}:/bin/bash" >> "$HOME/passwd"
    export LD_PRELOAD=libnss_wrapper.so
    export NSS_WRAPPER_PASSWD=${HOME}/passwd
    export NSS_WRAPPER_GROUP=/etc/group
}

function prepare_ssh_keys() {
    mkdir -p ${HOME}/.ssh/
    chown -R ${USER_ID}:0 ${HOME}/.ssh/
    chmod 0700 ${HOME}/.ssh/
    cp /etc/betka/id_rsa ${HOME}/.ssh/id_rsa
    cp /etc/betka/id_rsa.pub ${HOME}/.ssh/id_rsa.pub
    chmod 0600 ${HOME}/.ssh/{id_rsa,id_rsa.pub}
}

generate_passwd_file

mkdir -p ${HOME}/logs

if [ ! -f /etc/betka/id_rsa ]; then
    echo "SSH key mounted to (/etc/betka/id_rsa) is needed for working with downstream repositories."
    exit 1
fi

prepare_ssh_keys

# This suppresses adding authentication keys in ${HOME}/.ssh/known_host file
echo -e "Host *\n\tStrictHostKeyChecking no\n\tUserKnownHostsFile=/dev/null\n" >> ${HOME}/ssh_config
# For now, add both pagure instances into known_host
# TODO Fix this so known_hosts are not used at all.
ssh-keyscan src.fedoraproject.org >> ${HOME}/.ssh/known_hosts
ssh-keyscan pkgs.fedoraproject.org >> ${HOME}/.ssh/known_hosts

export GIT_SSL_NO_VERIFY=true
export GIT_SSH_COMMAND="ssh -i ${HOME}/.ssh/id_rsa  -F ${HOME}/ssh_config"

export LC_ALL="C"
# This part can be used for LOCAL TESTING
# exec python3 /home/betka/tasks.py
exec celery worker -A tasks -Q queue.betka-fedora --loglevel=debug --concurrency=1
