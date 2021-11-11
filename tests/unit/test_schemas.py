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

from pathlib import Path

import jsonschema
import pytest
from yaml import safe_load

from betka.schemas import BotCfg


class TestSchemas:
    """
    Test schemas.py
    """

    @pytest.fixture
    def example_bot_cfg(self):
        path = Path(__file__).parent.parent / "data/bot-configs/bot-cfg.yml"
        return safe_load(open(path))

    @pytest.fixture
    def bad_cfg(self):
        path = Path(__file__).parent.parent / "data/bot-configs/bad-cfg.yml"
        return safe_load(open(path))

    def test_example_bot_cfg(self, example_bot_cfg):
        jsonschema.validate(example_bot_cfg, BotCfg.get_schema())

    def test_bad_bot_cfg(self, bad_cfg):
        with pytest.raises(jsonschema.exceptions.ValidationError):
            jsonschema.validate(bad_cfg, BotCfg.get_schema())
