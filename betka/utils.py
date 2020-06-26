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


import logging
import shutil
import os
import json

from pathlib import Path
from contextlib import contextmanager
from betka.constants import HOME

logger = logging.getLogger(__name__)


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
