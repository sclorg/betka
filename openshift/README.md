This directory contains OpenShift resource configuration files (`.j2` means Jinja2 template).

Prerequisite is to have stored API tokens in `../secrets.env` which is copy from `../secrets.template`.

Copy file `vars/templates.yml` to `vars/prod.yml` and fill the variables.

Create a dir `ssh-pagure` and copy your SSH keys for access to Pagure.
