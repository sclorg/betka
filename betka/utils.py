# MIT License
#
# Copyright (c) 2020 SCL team at Red Hat
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


from contextlib import contextmanager
import logging
import shutil
import os
import json

import jinja2
import subprocess

from pathlib import Path
from betka.constants import HOME

logger = logging.getLogger(__name__)


def run_cmd(cmd, return_output=False, ignore_error=False, shell=False, **kwargs):
    """
    Run provided command on host system using the same user as invoked this code.
    Raises subprocess.CalledProcessError if it fails.

    :param cmd: list or str
    :param return_output: bool, return output of the command
    :param ignore_error: bool, do not fail in case nonzero return code
    :param shell: bool, run command in shell
    :param kwargs: pass keyword arguments to subprocess.check_* functions; for more info,
            please check `help(subprocess.Popen)`
    :return: None or str
    """
    logger.debug("command: %r", cmd)
    try:
        if return_output:
            return subprocess.check_output(
                cmd,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                shell=shell,
                **kwargs,
            )
        else:
            return subprocess.check_call(cmd, shell=shell, **kwargs)
    except subprocess.CalledProcessError as cpe:
        if ignore_error:
            if return_output:
                return cpe.output
            else:
                return cpe.returncode
        else:
            logger.error(f"failed with code {cpe.returncode} and output:\n{cpe.output}")
            raise cpe


def text_from_template(template_dir, template_filename, template_data):
    """
    Create text based on template in path template_dir/template_filename
    :param template_dir: string, directory containing templates
    :param template_filename: template for text in jinja
    :param template_data: dict, data for substitution in template
    :return: string
    """

    if not os.path.exists(os.path.join(template_dir, template_filename)):
        raise FileNotFoundError("Path to template not found.")

    template_loader = jinja2.FileSystemLoader(searchpath=template_dir)
    template_env = jinja2.Environment(loader=template_loader)
    template = template_env.get_template(template_filename)
    output_text = template.render(template_data=template_data)
    logger.debug("Text from template created:")
    logger.debug(output_text)

    return output_text


def copy_upstream2downstream(src_parent: Path, dest_parent: Path):
    """Copies content from upstream repo to downstream repo

    Copies all files/dirs/symlinks from upstream source to dist-git one by one,
    while removing previous if exists.

    :param src_parent: path to source directory
    :param dest_parent: path to destination directory
    """
    for f in src_parent.iterdir():
        if f.name.startswith(".git"):
            continue
        dest = dest_parent / f.name
        src = src_parent / f.name
        logger.debug(f"Copying {str(src)} to {str(dest)}.")
        # First remove the dest only if it is not symlink.
        if dest.is_dir() and not dest.is_symlink():
            logger.debug("rmtree %s", dest)
            shutil.rmtree(dest)
        else:
            if dest.exists():
                dest.unlink()

        # Now copy the src to dest
        if src.is_symlink() or not src.is_dir():
            logger.debug("cp %s %s", src, dest)
            shutil.copy2(src, dest, follow_symlinks=False)
        else:
            logger.debug("cp -r %s %s", src, dest)
            shutil.copytree(src, dest, symlinks=True)


def clean_directory(path: Path):
    """
    Function cleans directory except itself
    :param path: directory path which is cleaned
    """
    for d in path.iterdir():
        src = path / d
        if src.is_dir():
            logger.debug("rmtree %s", str(src))
            shutil.rmtree(src)
        else:
            src.unlink()


def list_dir_content(dir_name: Path):
    """
    Lists all content of dir_name
    :param dir_name: Directory for showing files
    """
    logger.info("Look for a content in '%s' directory", str(dir_name))
    for f in dir_name.rglob("*"):
        if str(f).startswith(".git"):
            continue
        logger.debug(f"{f.parent / f.name}")


def load_config_json():
    with open(f"{HOME}/config.json") as config_file:
        data = json.load(config_file)
    return data


@contextmanager
def cwd(path):
    """
    Switch to Path directory and once action is done
    returns back
    :param path:
    :return:
    """
    prev_cwd = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev_cwd)
