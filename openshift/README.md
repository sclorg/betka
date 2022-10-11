This directory contains OpenShift resource configuration files (`.j2` means Jinja2 template).

## Prerequisities

Store your API tokens in `../secrets.env` which is copy from `../secrets.template`.
Create the file `sentry.dsn` in the directory `openshift` and place there your DSN entry.
Copy file `vars/templates.yml` to `vars/prod.yml` and fill the variables.

Create a dir `ssh-gitlab` and copy your SSH keys for access to GitLab.
