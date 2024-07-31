from typing import (
    Generator,
    Tuple,
    List,
    Callable,
    Iterator,
)

import os
import sys
import re
import logging
from enum import Enum

FILE = "test.info"

logger = logging.getLogger()


class MyLine:
    def __init__(
        self,
        filename: str,
        line: str,
        line_nr: int,
    ):
        self.filename = filename
        self.line_nr = line_nr
        self.line = line


class TokenType(Enum):
    NONE = 0
    STRING = 1
    WORD = 2
    GROUP_START = 3
    GROUP_END = 4
    LINE_CONTINUE = 5
    LINE_END = 6


class MyToken:
    def __init__(
        self,
        line: MyLine,
        string: str,
        t_type: TokenType,
        start: int,
    ):
        self.line = line
        self.string = string
        self.string = string
        self.t_type = t_type
        self.start = start


class TokenStreamerFromFile:
    escapes = {
        "0": "\0",
        "a": "\a",
        "b": "\b",
        "f": "\f",
        "n": "\n",
        "r": "\r",
        "t": "\t",
        "v": "\v",
        "'": "'",
        '"': '"',
        "\\": "\\",
    }

    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.f = open(filename, "r", encoding="utf-8")
        self.file_iterator = iter(self.f)
        self.comment_start = ";"
        self.line: str | None = None
        self.line_nr = 0
        self.stack: List[Callable] = []
        self.realpath = os.path.realpath(filename)
        self.myLine: MyLine | None = None

    def read_file(self) -> Generator[MyLine, None, None]:
        for self.line in self.file_iterator:
            self.line_nr += 1
            self.line = self.line.strip()

            if len(self.line) == 0 or self.line[0] == self.comment_start:
                continue

            if self.line.startswith(
                "#include"
            ):  # currently no recursive include myself test
                # DOTO: if the realpath of the file to include is myself abort
                include = self.line.split()[1].strip('"')
                tsff = TokenStreamerFromFile(include)
                yield from tsff.read_file()
            else:
                yield MyLine(
                    filename=self.filename, line_nr=self.line_nr, line=self.line
                )

    def string_reader(self, line: str, what: str) -> Tuple[str, str]:
        """read a string starting with a quote char specified in :what
        (single quote or doulbe quote)

        interprete escape seq 0 a b f n r t v ' " \
        and allow escaped string chars in the string
        count the length of the string (including the escape chars

        return:
        (the modified line :the extracted string is removed from the front of the line)
        and:
        (the extracted string minus the beginning and ending quote char)
        """
        maxlen = len(line)
        result = ""  # the resulting string including beginning and ending quote

        current = 0
        length = 0
        result += what

        while current < maxlen:
            current += 1  # advance
            length += 1

            if line[current] == "\\":  # we see a escape char in the string
                if line[current + 1] not in self.escapes:
                    raise Exception(
                        f"Error: unknown escape in string: {line[current:current+1]}"
                    )
                current += 1
                length += 1
                result += self.escapes[line[current]]
                continue

            if line[current] != what:
                result += line[current]
                continue

            assert line[current] == what
            result += line[current]
            return line[length + 1 :], result

        return line, ""

    def read_tokens_raw(self) -> Generator[str, None, None]:
        iterator = iter(self.read_file())
        for self.myLine in iterator:
            self.line = self.myLine.line.strip()
            while len(self.line) > 0:
                self.line = self.line.strip()
                if self.line[0] == self.comment_start:
                    break

                if self.line[0] in ["'", '"']:
                    self.line, string = self.string_reader(self.line, self.line[0])
                    token = string
                    self.line = self.line.strip()
                    yield token
                    continue

                if self.line[0] == "{":
                    token = self.line[0]
                    self.line = self.line[len(token) :].strip()
                    yield token
                    continue

                if self.line[0] == "}":
                    token = self.line[0]
                    self.line = self.line[len(token) :].strip()
                    yield token
                    continue

                if self.line[0] == "\\":
                    token = self.line[0]
                    self.line = self.line[len(token) :].strip()
                    yield token
                    continue

                # read a token from the beginning of the self.line
                # ; and whitespace (and {}) can only happen as value inside a string not otherwise
                match = re.match(r"[^\s;{}]+", self.line)
                if match:
                    token = match.group(0)
                    self.line = self.line[len(token) :].strip()
                    yield token
                    continue

                print("NO_MATCH", len(self.line), self.line)

            yield "\n"

    def do_line_continue_and_merge_strings(
        self,
        iterator: Iterator[str],
    ) -> Generator[str, None, None]:
        last = None
        for token in iterator:
            if token[0] not in ["'", '"'] and token != "\\":
                if last is not None:
                    yield last  # we are not merging so emit the string
                    last = None
                yield token
                continue

            if token != "\\":
                if last:
                    yield last
                last = token  # store the last string
            else:
                ll = "Error: line continuation:"
                zz = f"{self.line_nr}, {self.line}"

                if last is None:
                    raise Exception(f"{ll} only after a string; {zz}")

                try:
                    next_token = next(iterator)
                    if next_token != "\n":
                        raise Exception(
                            f"{ll} a '\\' only directly before newline; {zz}, {next_token}"
                        )

                    next_token = next(iterator)
                    if next_token[0] not in ["'", '"'] or last[0] not in ["'", '"']:
                        raise Exception(
                            f"{ll} we expext a string before and after '\\'; {zz}"
                        )

                    if last[0] != next_token[0]:
                        raise Exception(
                            "Error: string merge: "
                            + "we can only merge strings starting with "
                            + f"identical first character; {zz}"
                        )
                    # we may have multiple continuation lines so hang on to the new last
                    last = last[:-1] + next_token[1:]
                    continue

                except StopIteration:
                    yield token

    def _optimize_stream_br_close_before(
        self,
        iterator: Iterator[str],
    ) -> Generator[str, None, None]:
        last = None
        for token in iterator:
            if token == "}":
                if last != "\n":
                    yield "\n"
            yield token
            last = token

    def _optimize_stream_br_open1(
        self,
        iterator: Iterator[str],
    ) -> Generator[str, None, None]:
        for token in iterator:
            if token != "{":
                yield token
                continue

            try:
                next_token = next(iterator)
                if next_token != "\n":
                    yield token
                    yield "\n"
                    yield next_token
                else:
                    yield token
                    yield next_token
            except StopIteration:
                yield token

    def _optimize_stream_br_open2(
        self,
        iterator: Iterator[str],
    ) -> Generator[str, None, None]:
        for token in iterator:
            if token == "\n":
                try:
                    next_token = next(iterator)
                    if next_token == "{":
                        yield next_token
                    else:
                        yield token
                        yield next_token
                except StopIteration:
                    yield token
            else:
                yield token

    def _optimize_stream_br_close(
        self,
        iterator: Iterator[str],
    ) -> Generator[str, None, None]:
        for token in iterator:
            if token == "}":
                try:
                    next_token = next(iterator)
                    if next_token != "\n":
                        yield token
                        yield "\n"
                        yield next_token
                    else:
                        yield token
                        yield next_token
                except StopIteration:
                    yield token
            else:
                yield token

    def _optimize_stream_br_close2(
        self,
        iterator: Iterator[str],
    ) -> Generator[str, None, None]:
        """if we see multiple }}}}, we need a second step to remove the odd }"""
        for token in iterator:
            if token == "}":
                try:
                    next_token = next(iterator)
                    if next_token != "\n":
                        yield token
                        yield "\n"
                        yield next_token
                    else:
                        yield token
                        yield next_token
                except StopIteration:
                    yield token
            else:
                yield token

    def prep(self) -> Generator[str, None, None]:
        # possibly later allow for dynamic filters
        i0 = self.read_tokens_raw()
        i1 = self.do_line_continue_and_merge_strings(i0)
        i2 = self._optimize_stream_br_close_before(i1)
        i3 = self._optimize_stream_br_open1(i2)
        i4 = self._optimize_stream_br_open2(i3)
        i5 = self._optimize_stream_br_close(i4)
        i6 = self._optimize_stream_br_close2(i5)
        return i6

    def stream(self) -> Generator[str, None, None]:
        for token in self.prep():
            yield token


def setup():
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
    logger.info("Started")


def main():
    setup()
    tsff = TokenStreamerFromFile(FILE)
    for token in tsff.stream():
        print(f"{token}", end="")


main()
