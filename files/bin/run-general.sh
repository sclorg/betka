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

generate_passwd_file

mkdir -p ${HOME}/logs

if [ ! -f ${HOME}/.ssh/id_rsa ]; then
    echo "SSH key mounted to (~/.ssh/id_rsa) is needed for working with downstream repositories."
    exit 1
fi

# This suppresses adding authentication keys in ${HOME}/.ssh/known_host file
echo -e "Host *\n\tStrictHostKeyChecking no\n\tUserKnownHostsFile=/dev/null\n" >> ${HOME}/ssh_config
export GIT_SSL_NO_VERIFY=true
export GIT_SSH_COMMAND="ssh -i ${HOME}/.ssh/id_rsa  -F ${HOME}/ssh_config"

export LC_ALL="C"
