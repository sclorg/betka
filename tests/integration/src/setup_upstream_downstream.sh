#!/bin/sh

UPSTREAM=$1
DOWNSTREAM=$2

mkdir -p ${UPSTREAM} ${DOWNSTREAM}

cp bot-cfg.yml ${UPSTREAM}
cd ${UPSTREAM}
git init .
echo "Testing repo" >> README.md
git add README.md
git commit -m "Initial commit"
git config user.name "Testy McTestFace" && git config user.email "mtestface@testing.org"

# create new branch without bot-cfg.yml
git checkout -b fc30
echo "fc30" >> README.md
git add README.md
git commit -m "Init branch"

# create a new branch with bot-cfg.yml
git checkout master
git checkout -b fc31
git add bot-cfg.yml
git commit -m "Add bot-cfg.yml"

cp -r ${UPSTREAM}/. ${DOWNSTREAM}

# "update" upstream with some changes
#echo "Update" >> README.md
#git add README.md
#git commit -m "readme update"
