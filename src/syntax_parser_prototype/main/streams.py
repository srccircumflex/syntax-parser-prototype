from __future__ import annotations

from collections import deque
from io import StringIO
from typing import Any, TYPE_CHECKING, Pattern, Callable, Literal, Iterable

if TYPE_CHECKING:
    from . import phrase
    from ..features import tokenize
    from . import tokens

from ..exceptions import *

__all__ = (
    "TokenizeStream",
    "DefaultTokenizeStream",
    "Stream",
    "Parser",
)


class TokenizeStream:
    r"""Tokenizer stream is a sub-stream that is passed to the ``Phrase.tokenize`` method (if defined)
    and allows the dedicated tokenization of the designated part of a row.

    The stream repeatedly calls ``Phrase.tokenize`` until the stream is exhausted.

    :ivar delimiter: Delimiter token that defines the end of the designated content or None for the row end.
    :type delimiter: NodeToken | EndToken | Token | None
    :ivar designated: The content of the part of the row intended for tokenization.
    :type designated: str
    :ivar i: Counter that tracks the number of tokenization calls in the stream.
    :type i: int
    :ivar context: Context in which the tokenizer operates, specified as
        **"<"** *lstrip* (feature ``LStrip``),
        **"i"** *inner* (designed inner content of a branch),
        **">"** *rtokenize* (feature ``RTokenize``).
    :type context: Literal["<", "i", ">"]
    :ivar unparsed: `<property>` unparsed/untokenized part of the designated content.
    :type unparsed: str
    :ivar parsed: `<property>` parsed/tokenized part of the designated content.
    :type parsed: str
    :ivar eat_n: `<method>` advance the stream by `n` characters of the unparsed content and return them.
    :ivar eat_remain: `<method>` advance the stream to the end and return the rest of the unparsed content.
    :ivar eat_until: `<method>` advance the stream to the beginning of the matching `regex` in the unparsed
        part and return this advanced content (exclusive matching content);
        or consume and return the rest of the unparsed content if no match was found and `strict` is ``False`` (default),
        otherwise ``None``
    :ivar eat_while: `<method>` commit character by character from the unparsed content and advance the stream as long as the function call returns a truth value, then return the sum.
    """

    __stream__: Stream
    """main stream object"""
    __at__: int
    """start point of the current token in the designated part"""
    __buffer__: StringIO
    """buffer for current token content"""
    __cursor__: int
    """current cursor position in the designated part"""
    __feat_token__: tokens.T_BASE_TOKENS
    """the token that triggers tokenization (special interface for features)"""

    delimiter: tokens.T_BASE_TOKENS | None | tokenize.RTokenize
    """which delimits the designated content (None for row end)"""
    designated: str
    """the designated content"""
    i: int
    """iteration counter"""
    context: Literal["<", "i", ">"]
    """context in which the tokenizer operates: LStrip, inner or RTokenize."""

    def __init__(
            self,
            stream: Stream,
            delimiter: tokens.T_BASE_TOKENS | None | tokenize.RTokenize,
            __feat_token__: tokens.T_BASE_TOKENS,
            context: Literal["<", "i", ">"] = "i",
    ):
        self.__stream__ = stream
        self.__feat_token__ = __feat_token__
        self.delimiter = delimiter
        self.context = context
        self.__at__ = -1
        self.__cursor__ = 0
        self.designated = self.__stream__.row[
            slice(
                self.__stream__.__position__,
                self.delimiter.column_start if self.delimiter else None
            )
        ]

    @property
    def unparsed(self) -> str:
        """look up unparsed part of the designated content"""
        return self.designated[self.__cursor__:]

    @property
    def parsed(self) -> str:
        """parsed part of the designated content"""
        return self.designated[:self.__cursor__]

    def eat_n(self, n: int = 1) -> str:
        """advance the stream by `n` characters of the unparsed content and return them"""
        self.__buffer__.write(c := self.designated[self.__cursor__:self.__cursor__ + n])
        self.__cursor__ += n
        return c

    def eat_remain(self) -> str:
        """advance the stream to the end and return the rest of the unparsed content"""
        self.__buffer__.write(c := self.designated[self.__cursor__:])
        self.__cursor__ = len(self.designated)
        return c

    def eat_until(self, regex: Pattern[str], strict: bool = False) -> str | None:
        """advance the stream to the beginning of the matching `regex` in the unparsed
        part and return this advanced content (exclusive matching content);
        or consume and return the rest of the unparsed content if no match was found and `strict` is ``False`` (default),
        otherwise ``None``
        """
        if m := regex.search(self.unparsed):
            self.__buffer__.write(c := self.unparsed[:m.start()])
            self.__cursor__ += m.start()
            return c
        elif strict:
            return None
        else:
            return self.eat_remain()

    def eat_while(self, f: Callable[[str], bool | Any]) -> str:
        """commit character by character from the unparsed content and advance the stream
        as long as the function call returns a truth value, then return the sum
        """
        buffer = StringIO()
        while self.unparsed and f(self.unparsed[0]):
            buffer.write(self.eat_n(1))
        return buffer.getvalue()

    def __istart__(self):
        if self.unparsed:
            if self.__at__ == self.__cursor__:
                raise TokenizationAdvanceError(self)
            self.__buffer__ = StringIO()
            return True
        else:
            return False

    def __run__(self):
        node = self.__stream__.node
        tokenize = self.__feat_token__.__feat_phrase__.tokenize
        self.i = 0
        while self.__istart__():
            self.__at__ = self.__cursor__
            node.inner.append(tokenize(self)(
                at=self.__at__,
                to=-00,
            ).__ini_from_tokenize__(self.__buffer__.getvalue(), self))
            self.i += 1


class DefaultTokenizeStream(TokenizeStream):
    """Modification of ``TokenizeStream`` that parses the entire designated content to
    ``Phrase.TDefaultToken`` (saves operations if ``Phrase.tokenize`` is not defined)"""

    def __run__(self):
        self.__stream__.node.inner.append(
            self.__feat_token__.__feat_phrase__.TDefaultToken(
                at=0,
                to=-00,
            ).__ini_from_tokenize__(self.designated, self)
        )


class Stream:
    """The stream is used to parse lines of text and is passed as a pure state object to the
    methods “Phrase.starts” and “Phrase.ends”
    (**mutations should not be performed by user code**).

    :ivar row: The current row being parsed.
    :type row: str
    :ivar buffer: Remaining unparsed rows stored in a deque.
    :type doc: deque[str]
    :ivar node: The currently active node in the parsing process.
    :type node: NodeToken
    :ivar row_no: Counter for rows processed.
    :type row_no: int
    :ivar viewpoint: The current viewpoint in the row being parsed.
    :type viewpoint: int
    :ivar unparsed: `<property>` unparsed/untokenized part of the current row.
    :type unparsed: str
    :ivar parsed: `<property>` parsed/tokenized part of the current row.
    :type parsed: str
    """

    row: str
    """current row to parse"""
    buffer: deque[str]
    """remain unparsed rows"""
    node: tokens.NodeToken
    """current active node"""
    row_no: int
    """row count"""
    viewpoint: int
    """viewpoint in current row"""

    __position__: int
    """usually reflects viewpoint, only acts as a separate data anchor in a masking area"""

    @property
    def unparsed(self) -> str:
        """remain unparsed part of the current row"""
        return self.row[self.viewpoint:]

    @property
    def parsed(self) -> str:
        """parsed part of the current row"""
        return self.row[:self.viewpoint]


class Parser(Stream):
    entry: tokens.RootNode | tokens.NodeToken
    """the entry node"""
    root: tokens.RootNode
    """the root node"""

    __suffix_phrases__: set[phrase.Phrase] | None
    """suffix phrases to be searched for"""

    def __init__(
            self,
            doc: Iterable[str],
            entry: tokens.RootNode | tokens.NodeToken,
            row: str = "",
            row_no: int = 0,
            viewpoint: int = 0,
            __position__: int = 0,
            __suffix_phrases__: set[phrase.Phrase] | None = None,
    ):
        self.row = row
        self.buffer = deque(doc)
        self.entry = self.node = entry
        self.root = entry.root
        self.row_no = row_no
        self.viewpoint = viewpoint
        self.__position__ = __position__
        self.__suffix_phrases__ = __suffix_phrases__

    def __nextrow__(self):
        """move to the next row"""
        try:
            self.row = self.buffer.popleft()
            self.root.tokenIndex.__at_row__(self)
        except IndexError:
            raise EOFError
        else:
            self.row_no += 1
            self.viewpoint = self.__position__ = 0

    def __carry__(self, n: int):
        """advance viewpoint and __pos__ by n"""
        self.viewpoint = self.__position__ = self.viewpoint + n

    def __carby__(self, item: tokens.T_START_TOKENS):
        """advance viewpoint and __pos__ to the end of a parsed token"""
        self.__carry__(item.__to__)
        if self.viewpoint >= len(self.row):
            self.__nextrow__()

    def __mask_continue__(self):
        """search for a mask continuation, otherwise return the found non-mask token"""
        active_stop = self.node.__ends__(self)

        item: tokens.Token | tokens.MaskToken | tokens.MaskNodeToken
        if item := self.__search_sub__():
            if active_stop and active_stop < item:
                return active_stop
            elif not item.__fMASK__:
                return item
            else:
                item: tokens.MaskToken | tokens.MaskNodeToken
                item.__ini_as_node__(self)
                return self.__mask_item__(item)
        elif active_stop:
            return active_stop
        else:
            self.node.phrase.TTokenizeStream(self, None, self.node).__run__()
            self.__nextrow__()
            return self.__mask_continue__()

    def __mask_item__(self, mask: tokens.MaskToken | tokens.MaskNodeToken):
        """process a mask token"""

        if mask.__to__ == 0:
            raise NullTokenError(self, mask)

        self.viewpoint += mask.__to__

        if self.viewpoint >= len(self.row):
            self.node.phrase.TTokenizeStream(self, None, self.node).__run__()
            self.__nextrow__()

        if mask.__fNODE__:
            while not (e := mask.__ends__(self)):
                self.node.phrase.TTokenizeStream(self, None, self.node).__run__()
                self.__nextrow__()
            e.__ini_as_token__(self)
            self.viewpoint += e.__to__

        return self.__mask_continue__()

    def __masking__(self, mask: tokens.MaskToken | tokens.MaskNodeToken):
        """masking entry point"""
        end = self.__mask_item__(mask)
        end.__viewpoint__ = self.viewpoint
        self.node.phrase.TTokenizeStream(self, end, self.node).__run__()
        self.viewpoint = self.__position__ = self.viewpoint + end.__at__

    def __sub_item__(self, item: tokens.T_START_TOKENS):
        """start a node or handle stand-alone-token"""
        item.__ini_as_node__(self)
        if item.__fMASK__:
            item: tokens.MaskToken | tokens.MaskNodeToken
            # masking
            self.__masking__(item)
        else:
            if item.__at__:
                # remain token
                self.node.phrase.TTokenizeStream(self, item, self.node).__run__()
            item.__featurize__(self)
        return item

    def __end_item__(self, end: tokens.EndToken):
        """end a phrase"""
        end.__ini_as_token__(self)
        if end.__at__:
            # remain token
            self.node.phrase.TTokenizeStream(self, end, self.node).__run__()
        end.__featurize__(self)
        return end

    def __search_phrase__(self, phrases: set[phrase.Phrase]) -> tokens.T_START_TOKENS | None:
        item: tokens.T_START_TOKENS | None = None
        __iter__ = iter(phrases)

        try:
            while item is None:
                ph = next(__iter__)
                if _itm := ph.starts(self):
                    _itm.phrase = ph
                    if _itm.__fINSTANT__:
                        return _itm
                    else:
                        item = _itm
        except StopIteration:
            # no start found for any phrase
            return None

        # a start found
        # search in the rest of the phrases and compare priority
        for ph in __iter__:
            if _itm := ph.starts(self):
                _itm.phrase = ph
                if _itm.__fINSTANT__:
                    return _itm
                elif _itm < item:
                    item = _itm

        return item

    def __search_suffix__(self) -> tokens.T_START_TOKENS | None:
        """search for suffix phrase"""
        if phrases := self.__suffix_phrases__:
            self.__suffix_phrases__ = None
            if (item := self.__search_phrase__(phrases)) and item.__at__ == 0:
                return item
        return None

    def __search_sub__(self) -> tokens.T_START_TOKENS | None:
        """search for sub phrase"""
        return self.__search_phrase__(self.node.phrase.__sub_phrases__)

    def __iteration__(self) -> tokens.T_BASE_TOKENS | None:
        """main iteration"""
        end = self.node.__ends__(self)

        if end and end.__fINSTANT__:
            return self.__end_item__(end)
        else:
            if suffix_item := self.__search_suffix__():
                return self.__sub_item__(suffix_item)
            elif sub_item := self.__search_sub__():
                if sub_item.__fINSTANT__:
                    return self.__sub_item__(sub_item)
                elif end and end < sub_item:
                    return self.__end_item__(end)
                else:
                    return self.__sub_item__(sub_item)
            elif end:
                return self.__end_item__(end)
            else:
                self.node.phrase.TTokenizeStream(self, None, self.node).__run__()
                self.__nextrow__()
                return None

    def __run__(self) -> None:
        try:
            if not self.row:
                try:
                    self.row = self.buffer.popleft()
                except IndexError:
                    raise EOFError
                self.root.tokenIndex.__at_row__(self)
            else:
                self.root.tokenIndex.__at_stale__(self)
            while True:
                row_no, viewpoint = self.row_no, self.viewpoint
                token = self.__iteration__()
                if token and (
                        token.__fNODE__
                        or  # stand-alone token
                        not token.__fEND__
                ):
                    # node and stand-alone tokens must advance the stream
                    if not (row_no != self.row_no or viewpoint != self.viewpoint):
                        raise NullTokenError(self, token)
        except EOFError:
            self.root.tokenIndex.__build__()
