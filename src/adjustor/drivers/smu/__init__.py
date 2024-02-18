from typing import Any, Sequence, TYPE_CHECKING
import os
from hhd.plugins import (
    HHDPlugin,
    Context,
)
from hhd.plugins import load_relative_yaml
import logging

from hhd.plugins.conf import Config

logger = logging.getLogger(__name__)


class SmuDriverPlugin(HHDPlugin):
    def __init__(self) -> None:
        self.name = f"adjustor_smu"
        self.priority = 7
        self.log = "asmu"

    def settings(self):
        return {
            "tdp": {
                "adjustor": {
                    "type": "container",
                    "children": {
                        "smu": load_relative_yaml("smu.yml"),
                    },
                }
            }
        }

    def open(
        self,
        emit,
        context: Context,
    ):
        pass

    def update(self, conf: Config):
        pass

    def close(self):
        pass