from typing import (
    Any,
)

import os
import sys
import logging

import yaml

from py_read_info import InfoTokenStreamerFromFile
from py_read_info import InfoParser

logger = logging.getLogger()


class MyDumper(yaml.Dumper):  # pylint: disable=R0901; Too many ancestors
    def increase_indent(
        self,
        flow: bool = False,
        indentless: bool = False,
    ) -> Any:
        return super().increase_indent(flow, False)


def setup() -> None:
    prog = os.path.basename(sys.argv[0])
    if prog.lower().endswith(".py"):
        prog = prog[:-3]

    logging.basicConfig(
        filename=f"{prog}.log",
        encoding="utf-8",
        level=logging.DEBUG,
        format=" ".join(
            [
                "%(asctime)s",
                "%(levelname)s",
                "%(filename)s:%(lineno)s:%(funcName)s",
                "%(message)s",
            ]
        ),
    )


def main() -> None:
    setup()

    itsff = InfoTokenStreamerFromFile(filename=sys.argv[1])
    ip = InfoParser(streamer=itsff)

    r = ip.process()
    s = yaml.dump(
        r,
        Dumper=MyDumper,
        default_flow_style=False,
    )
    print(s, end="")


main()
