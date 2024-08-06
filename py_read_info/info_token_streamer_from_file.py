from typing import (
    Generator,
    Tuple,
    Iterator,
)

import os
import re
import logging

from .info_line import InfoLine
from .info_token import (
    InfoToken,
    InfoTokenType,
)

MAX_INCLUDE_DEPTH: int = 100

logger = logging.getLogger(__name__)


class InfoTokenStreamerFromFile:  # pylint: disable=R0902 ; too_many_instance_attributes
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

    def __init__(
        self,
        *,
        filename: str,
        include_depth: int = 0,
    ) -> None:
        self.filename = filename
        self.f = open(filename, "r", encoding="utf-8")  # pylint: disable=R1732
        self.file_iterator = iter(self.f)
        self.comment_start = ";"
        self.line: str | None = None
        self.line_nr = 0
        self.realpath = os.path.realpath(filename)
        self.my_line: InfoLine | None = None
        self.include_depth = include_depth
        if self.include_depth > MAX_INCLUDE_DEPTH:
            raise Exception(f"Fatal: too many levels of include: {include_depth}")
        logger.debug("read from file: %s, level %d", self.realpath, self.include_depth)

    def read_file(self) -> Generator[InfoLine, None, None]:
        for self.line in self.file_iterator:
            self.line_nr += 1
            self.line = self.line.strip()

            if len(self.line) == 0 or self.line[0] == self.comment_start:
                continue

            if self.line.startswith("#include"):
                here = os.path.dirname(self.realpath)
                # relative includes are relative to the current file
                include = self.line.split()[1].strip('"')
                if include[0] != "/":  # on unix
                    include = here + "/" + include
                if os.path.realpath(include) == self.realpath:
                    raise Exception(f"Fatal: include cannot refer to the current file; {include} == {self.realpath}")

                tsff = InfoTokenStreamerFromFile(
                    filename=include,
                    include_depth=self.include_depth + 1,
                )
                yield from tsff.read_file()
            else:
                yield InfoLine(
                    filename=self.filename,
                    line_nr=self.line_nr,
                    line=self.line,
                )

    def string_reader(
        self,
        line: str,
        what: str,
    ) -> Tuple[str, str]:
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
                    raise Exception(f"Error: unknown escape in string: {line[current:current+1]} in line: {line}")
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

    def read_tokens_raw(self) -> Generator[InfoToken, None, None]:
        iterator = iter(self.read_file())
        for self.my_line in iterator:
            assert self.my_line is not None
            self.line = self.my_line.line.strip()
            while len(self.line) > 0:
                self.line = self.line.strip()
                if self.line[0] == self.comment_start:
                    break

                if self.line[0] in ["'", '"']:
                    self.line, string = self.string_reader(self.line, self.line[0])
                    token = string
                    self.line = self.line.strip()
                    yield InfoToken(
                        line=self.my_line,
                        string=token,
                        t_type=InfoTokenType.STRING,
                        begin=0,
                    )
                    continue

                if self.line[0] == "{":
                    token = self.line[0]
                    self.line = self.line[len(token) :].strip()
                    yield InfoToken(
                        line=self.my_line,
                        string=token,
                        t_type=InfoTokenType.GROUP_START,
                        begin=0,
                    )
                    continue

                if self.line[0] == "}":
                    token = self.line[0]
                    self.line = self.line[len(token) :].strip()
                    yield InfoToken(
                        line=self.my_line,
                        string=token,
                        t_type=InfoTokenType.GROUP_END,
                        begin=0,
                    )
                    continue

                if self.line[0] == "\\":
                    token = self.line[0]
                    self.line = self.line[len(token) :].strip()
                    yield InfoToken(
                        line=self.my_line,
                        string=token,
                        t_type=InfoTokenType.LINE_CONTINUE,
                        begin=0,
                    )
                    continue

                # read a token from the beginning of the self.line
                # ; and whitespace (and {}) can only happen as value inside a string not otherwise
                match = re.match(r"[^\s;{}]+", self.line)
                if match:
                    token = match.group(0)
                    self.line = self.line[len(token) :].strip()
                    yield InfoToken(line=self.my_line, string=token, t_type=InfoTokenType.WORD, begin=0)
                    continue

                raise Exception(f"Fatal: unexpected data in line: {self.line_nr}: {self.line}")

            yield InfoToken(line=self.my_line, string="\n", t_type=InfoTokenType.LINE_END, begin=0)

    def do_line_continue_and_merge_strings(
        self,
        iterator: Iterator[InfoToken],
    ) -> Generator[InfoToken, None, None]:
        last = None
        for token in iterator:
            if token.string[0] not in ["'", '"'] and token.string != "\\":
                if last is not None:
                    yield last  # we are not merging so emit the string
                    last = None
                yield token
                continue

            if token.string != "\\":
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
                    if next_token.string != "\n":
                        raise Exception(f"{ll} a '\\' only directly before newline; {zz}, {next_token.string}")

                    next_token = next(iterator)
                    if next_token.string[0] not in ["'", '"'] or last.string[0] not in ["'", '"']:
                        raise Exception(f"{ll} we expext a string before and after '\\'; {zz}")

                    if last.string[0] != next_token.string[0]:
                        raise Exception(
                            "Error: string merge: "
                            + "we can only merge strings starting with "
                            + f"identical first character; {zz}"
                        )
                    # we may have multiple continuation lines so hang on to the new last
                    last.string = last.string[:-1] + next_token.string[1:]
                    continue

                except StopIteration:
                    yield token

    def _optimize_stream_br_close_before(
        self,
        iterator: Iterator[InfoToken],
    ) -> Generator[InfoToken, None, None]:
        last = None
        for token in iterator:
            assert self.my_line is not None

            if token.string == "}":
                assert last is not None
                if last.string != "\n":
                    yield InfoToken(line=self.my_line, string="\n", t_type=InfoTokenType.LINE_END, begin=0)
            yield token
            last = token

    def _optimize_stream_br_open1(
        self,
        iterator: Iterator[InfoToken],
    ) -> Generator[InfoToken, None, None]:
        for token in iterator:
            assert self.my_line is not None

            if token.string != "{":
                yield token
                continue

            try:
                next_token = next(iterator)
                if next_token.string != "\n":
                    yield token
                    yield InfoToken(line=self.my_line, string="\n", t_type=InfoTokenType.LINE_END, begin=0)
                    yield next_token
                else:
                    yield token
                    yield next_token
            except StopIteration:
                yield token

    def _optimize_stream_br_open2(
        self,
        iterator: Iterator[InfoToken],
    ) -> Generator[InfoToken, None, None]:
        for token in iterator:
            assert self.my_line is not None

            if token.string == "\n":
                try:
                    next_token = next(iterator)
                    if next_token.string == "{":
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
        iterator: Iterator[InfoToken],
    ) -> Generator[InfoToken, None, None]:
        for token in iterator:
            assert self.my_line is not None

            if token.string == "}":
                try:
                    next_token = next(iterator)
                    if next_token.string != "\n":
                        yield token
                        yield InfoToken(line=self.my_line, string="\n", t_type=InfoTokenType.LINE_END, begin=0)
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
        iterator: Iterator[InfoToken],
    ) -> Generator[InfoToken, None, None]:
        """if we see multiple }}}}, we need a second step to remove the odd }"""
        for token in iterator:
            assert self.my_line is not None

            if token.string == "}":
                try:
                    next_token = next(iterator)
                    if next_token.string != "\n":
                        yield token
                        yield InfoToken(line=self.my_line, string="\n", t_type=InfoTokenType.LINE_END, begin=0)
                        yield next_token
                    else:
                        yield token
                        yield next_token
                except StopIteration:
                    yield token
            else:
                yield token

    def prep(self) -> Generator[InfoToken, None, None]:
        # possibly later allow for dynamic filters
        i0 = self.read_tokens_raw()
        i1 = self.do_line_continue_and_merge_strings(i0)
        i2 = self._optimize_stream_br_close_before(i1)
        i3 = self._optimize_stream_br_open1(i2)
        i4 = self._optimize_stream_br_open2(i3)
        i5 = self._optimize_stream_br_close(i4)
        i6 = self._optimize_stream_br_close2(i5)
        return i6

    def stream(self) -> Generator[InfoToken, None, None]:
        for token in self.prep():
            yield token
