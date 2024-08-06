import logging

from dataclasses import dataclass

MAX_INCLUDE_DEPTH: int = 100

logger = logging.getLogger(__name__)


@dataclass
class InfoLine:
    filename: str
    line: str
    line_nr: int

    def __str__(self) -> str:
        return f"file: '{self.filename}', line: {self.line_nr}:{self.line}"
