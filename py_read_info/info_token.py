import logging

from enum import Enum
from dataclasses import dataclass

from .info_line import InfoLine

MAX_INCLUDE_DEPTH: int = 100

logger = logging.getLogger(__name__)


class InfoTokenType(Enum):
    NONE = 0
    STRING = 1
    WORD = 2
    GROUP_START = 3
    GROUP_END = 4
    LINE_CONTINUE = 5
    LINE_END = 6


@dataclass
class InfoToken:
    line: InfoLine
    string: str
    t_type: InfoTokenType
    begin: int

    def __str__(self) -> str:
        return f"token: '{self.string}' in line: {self.line}"
