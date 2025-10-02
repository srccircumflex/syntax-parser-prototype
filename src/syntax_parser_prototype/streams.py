from __future__ import annotations

from io import StringIO
from typing import Any, TYPE_CHECKING, Pattern, Callable, Literal

from collections import deque

if TYPE_CHECKING:
    from .phrases import *
    from .utils import *

from .tokens import *


__all__ = (
    "AdvanceError",
    "TokenizeStream",
    "NullTokenizeStream",
    "Stream",
)


class AdvanceError(RuntimeError):

    def __init__(self, stream: TokenizeStream | Stream):
        if isinstance(stream, TokenizeStream):
            super().__init__(
                f"{stream.__class__.__name__} stuck without advancing.\n"
                f"in node: {stream.__stream__.node!r}\n"
                f"row@{stream.__stream__.row_no}: {stream.__stream__.row!r}\n"
                f"unparsed@{stream.__stream__.viewpoint + stream.__cursor__}: {stream.unparsed!r}"
            )
        else:
            super().__init__(
                f"{stream.__class__.__name__} stuck without advancing.\n"
                f"in node: {stream.node!r}\n"
                f"row@{stream.row_no}: {stream.row!r}\n"
                f"unparsed@{stream.__pos__}: {stream.unparsed!r}"
            )


class TokenizeStream:
    __stream__: Stream
    """main stream object"""
    __seen_start__: int
    """start point of the current token in the designated part"""
    __buffer__: StringIO
    """buffer for current token content"""
    __cursor__: int
    """current cursor position in the designated part"""

    delimiter: NodeToken | EndToken | Token | NodeTokenizeFuture | None
    """which delimits the designated content (None for row end)"""
    designated: str
    """the designated content"""
    context: Literal["n", "i", "e"]

    def __init__(
            self,
            stream: Stream,
            delimiter: NodeToken | EndToken | Token | NodeTokenizeFuture | None,
            context: Literal["n", "i", "e"] = "i",
    ):
        """substream for tokenization"""
        self.__stream__ = stream
        self.delimiter = delimiter
        self.context = context
        self.__seen_start__ = -1
        self.__cursor__ = 0
        self.designated = self.__stream__.row[
            slice(
                self.__stream__.__pos__,
                self.delimiter.column_start if self.delimiter else None
            )
        ]

    @property
    def unparsed(self) -> str:
        """look up unparsed part of the designated content"""
        return self.designated[self.__cursor__:]

    def eat_n(self, n: int = 1) -> str:
        """advance the stream by n characters of the designated content and return them"""
        self.__buffer__.write(c := self.designated[self.__cursor__:self.__cursor__ + n])
        self.__cursor__ += n
        return c

    def eat_remain(self) -> str:
        """advance the stream to the end and return the rest of the designated content"""
        self.__buffer__.write(c := self.designated[self.__cursor__:])
        self.__cursor__ = len(self.designated)
        return c

    def eat_until(self, regex: Pattern) -> str | None:
        """advance the stream to the beginning of the matching pattern in the designated
        part and return this content (exclusive matching content) or None if no match was found
        """
        if m := regex.search(self.unparsed):
            self.__buffer__.write(c := self.unparsed[:m.start()])
            self.__cursor__ += m.start()
            return c
        else:
            return None

    def eat_while(self, f: Callable[[str], bool | Any]) -> str:
        """commit character by character from the designated content and advance the stream
        as long as the function call returns a truth value, then return the sum
        """
        buffer = StringIO()
        while self.unparsed and f(self.unparsed[0]):
            buffer.write(self.eat_n(1))
        return buffer.getvalue()

    def __istart__(self):
        if self.unparsed:
            if self.__seen_start__ == self.__cursor__:
                raise AdvanceError(self)
            self.__buffer__ = StringIO()
            return True
        else:
            return False

    def __run__(self):
        node = self.__stream__.node
        i = 0
        while self.__istart__():
            self.__seen_start__ = self.__cursor__
            node.inner.append(node.phrase.tokenize(self, i)(
                seen_start=self.__seen_start__,
                content=self.__buffer__.getvalue(),
            ).__ini_as_token__(self.__stream__))
            i += 1


class NullTokenizeStream(TokenizeStream):

    def __run__(self):
        self.__stream__.node.inner.append(
            self.__stream__.node.phrase.TNullToken(
                seen_start=0,
                content=self.designated,
            ).__ini_as_token__(self.__stream__)
        )


class Stream:
    row: str
    """current row to parse"""
    doc: deque[str]
    """remain unparsed rows"""
    node: NodeToken
    """current active node"""
    row_no: int = 0
    """row count"""
    viewpoint: int = 0
    """viewpoint in current row"""

    __pos__: int

    __suffix_phrases__: set[Phrase] | None

    def __init__(
            self,
            row: str,
            doc: list[str],
            node: NodeToken,
            row_no: int = 0,
            viewpoint: int = 0,
            __pos__: int = 0,
            __suffix_phrases__: set[Phrase] | None = None,
    ):
        self.row = row
        self.doc = deque(doc)
        self.node = node
        self.row_no = row_no
        self.viewpoint = viewpoint
        self.__pos__ = __pos__
        self.__suffix_phrases__ = __suffix_phrases__

    @property
    def unparsed(self) -> str:
        """remain unparsed part of the current row"""
        return self.row[self.viewpoint:]

    @property
    def parsed(self) -> str:
        """parsed part of the current row"""
        return self.row[:self.viewpoint]

    def __nextrow__(self):
        """move to the next row"""
        try:
            self.row = self.doc.popleft()
        except IndexError:
            raise EOFError
        else:
            self.row_no += 1
            self.viewpoint = self.__pos__ = 0

    def __carry__(self, n: int):
        self.viewpoint = self.__pos__ = self.viewpoint + n

    def __carby__(self, item: Token | NodeToken):
        """carry the viewpoint to the end of a parsed token"""
        self.__carry__(item.seen_end)
        if self.viewpoint >= len(self.row):
            self.__nextrow__()

    def __mask_continue__(self):
        active_stop = self.node.__ends__(self)

        if item := self.__search_sub__():
            if active_stop and active_stop < item:
                return active_stop
            elif not isinstance(item, MaskToken):
                return item
            else:
                item.__ini_as_node__(self)
                return self.__mask_item__(item)
        elif active_stop:
            return active_stop
        else:
            self.node.phrase.TTokenizeStream(self, None).__run__()
            self.__nextrow__()
            return self.__mask_continue__()

    def __mask_item__(self, mask: MaskToken | MaskNodeToken):
        self.viewpoint += mask.seen_end

        if self.viewpoint >= len(self.row):
            self.node.phrase.TTokenizeStream(self, None).__run__()
            self.__nextrow__()

        if isinstance(mask, MaskNodeToken):
            while not (e := mask.__ends__(self)):
                self.node.phrase.TTokenizeStream(self, None).__run__()
                self.__nextrow__()
            e.__ini_as_token__(self)
            self.viewpoint += e.seen_end

        return self.__mask_continue__()

    def __masking__(self, mask: MaskToken | MaskNodeToken):
        end = self.__mask_item__(mask)
        end.viewpoint = self.viewpoint
        self.node.phrase.TTokenizeStream(self, end).__run__()
        self.viewpoint = self.__pos__ = self.viewpoint + end.seen_start

    def __sub_item__(self, item: Token | NodeToken):
        """start a node or handle stand-alone-token"""
        item.__ini_as_node__(self)
        if isinstance(item, MaskToken):
            self.__masking__(item)
        else:
            if item.seen_start:
                # remain token
                self.node.phrase.TTokenizeStream(self, item).__run__()

            item.__featurize__(self)

    def __end_item__(self, end: EndToken):
        """end a node"""
        end.__ini_as_token__(self)
        if end.seen_start:
            # remain token
            self.node.phrase.TTokenizeStream(self, end).__run__()

        end.__featurize__(self)

    def __search_suffix__(self) -> NodeToken | None:
        """search for suffix phrase"""
        if self.__suffix_phrases__:
            suffix_starts = list()
            for xp in self.__suffix_phrases__:
                if suffix_node := xp.starts(self):
                    suffix_node.phrase = xp
                    suffix_starts.append(suffix_node)
            self.__suffix_phrases__ = None
            if suffix_starts and (item := min(suffix_starts)).seen_start == 0:
                return item
        return None

    def __search_sub__(self) -> NodeToken | Token | None:
        """search for sub phrase"""
        sub_starts = list()
        for sp in self.node.phrase.__sub_phrases__:
            if start_node := sp.starts(self):
                start_node.phrase = sp
                sub_starts.append(start_node)
        return min(sub_starts) if sub_starts else None

    def __iteration__(self):
        """main iteration"""
        end = self.node.__ends__(self)

        if isinstance(end, XEndToken):
            self.__end_item__(end)
        else:
            if suffix_item := self.__search_suffix__():
                self.__sub_item__(suffix_item)
            elif sub_item := self.__search_sub__():
                if isinstance(sub_item, XToken):
                    self.__sub_item__(sub_item)
                elif end and end.__vs_sub__(sub_item):
                    self.__end_item__(end)
                else:
                    self.__sub_item__(sub_item)
            elif end:
                self.__end_item__(end)
            else:
                self.node.phrase.TTokenizeStream(self, None).__run__()
                self.__nextrow__()

    def __run__(self):
        """main iteration"""
        try:
            while True:
                row_no, viewpoint, node = self.row_no, self.viewpoint, self.node
                self.__iteration__()
                if not (row_no != self.row_no or viewpoint != self.viewpoint or node is not self.node):
                    raise AdvanceError(self)
        except EOFError:
            return


























