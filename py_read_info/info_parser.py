from typing import (
    Dict,
    Any,
)

import logging

from .info_token_streamer_from_file import InfoTokenStreamerFromFile
from .info_token import InfoToken

logger = logging.getLogger(__name__)


class InfoParser:
    def __init__(
        self,
        *,
        streamer: InfoTokenStreamerFromFile,
    ) -> None:
        self.streamer = streamer
        self.stream = iter(self.streamer.stream())
        self.data: Dict[str, Any] = {}

    def expect_newline(
        self,
        what: InfoToken,
        x: str,
    ) -> None:
        zz = "Fatal: unexpected data after"
        if what.string != "\n":
            raise Exception(f"{zz} '{x}', we expect 'newline', we got {what.string}; {what}")

    def do_lines(  # pylint: disable=R0912; Too many branches
        self,
        where: Dict[str, Any],
    ) -> None:
        """
        ## 5 types of lines:
         - key nl
         - key value nl
         - key value { nl
         - key { nl
         - } nl
        """
        zz = "Fatal: unexpected data after"
        x = "{"
        while True:  # pylint:: disable=R1702; Too many nested blocks
            try:
                what = next(self.stream)

                if what.string == "}":
                    # we have }, group is complete
                    what = next(self.stream)
                    self.expect_newline(what, "}")
                    return

                # expect: key
                key = what

                what = next(self.stream)
                # expect: nl, { , value

                # we have nl, we can store the key -> value and go for the next line
                if what.string == "\n":
                    where[key.string] = None
                    continue

                # we have {, we can start a new group
                if what.string == "{":
                    what = next(self.stream)
                    self.expect_newline(what, "{")

                    if key.string not in where:
                        where[key.string] = {}
                    self.do_lines(where[key.string])
                    continue

                # we have a value
                value = what

                what = next(self.stream)
                # expect: nl, {
                if what.string not in ["{", "\n"]:
                    raise Exception(
                        ",".join(
                            [
                                f"{zz} 'key' 'value'",
                                f" we expect 'newline' or '{x}'",
                                f" we got {what.string}",
                                f"line: {what.line}",
                            ]
                        )
                    )

                if what.string == "\n":
                    if key.string in where:  # duplicate key
                        if where[key.string] == value.string:
                            # we have a duplicate record so no need to store
                            # DOTO: if the 2 values are of the same scalar type
                            continue

                        if isinstance(where[key.string], list):
                            if value.string not in where[key.string]:
                                where[key.string].append(value.string)
                        else:  # change to list and append
                            val = where[key.string]
                            where[key.string] = [val]
                            where[key.string].append(value.string)
                        continue

                    where[key.string] = value.string
                    continue

                # we have {
                what = next(self.stream)
                self.expect_newline(what, "{")

                if key.string not in where:
                    where[key.string] = {}
                if value.string not in where[key.string]:
                    where[key.string][value.string] = {}
                self.do_lines(where[key.string][value.string])

            except StopIteration:
                return  # but perhaps we are not yet complete

    def process(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        self.do_lines(result)
        return result
