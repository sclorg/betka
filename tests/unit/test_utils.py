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

"""Test utilities from utils.py"""

import pytest
from subprocess import CalledProcessError

from betka.utils import run_cmd


class TestUtils(object):
    """Test utilities from utils.py"""

    @pytest.mark.parametrize(
        "cmd, ok", [(["ls", "-la"], True), (["ls", "--nonexisting"], False)]
    )
    def test_run_cmd(self, cmd, ok):
        """Test run_cmd()."""
        if ok:
            assert run_cmd(cmd, return_output=True).startswith("total ")
            assert run_cmd(cmd, return_output=False) == 0
        else:
            with pytest.raises(CalledProcessError):
                run_cmd(cmd, ignore_error=False)
            assert run_cmd(cmd, ignore_error=True, return_output=True)
            assert run_cmd(cmd, ignore_error=True, return_output=False) > 0
