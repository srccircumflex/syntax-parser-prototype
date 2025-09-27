from __future__ import annotations

from collections.abc import Iterable
from io import StringIO
from typing import Any, Generator, overload, TYPE_CHECKING, Type, Pattern, Callable

if TYPE_CHECKING:
    from typing_extensions import Self


class AdvanceError(RuntimeError):

    def __init__(self, stream: TokenizeStream):
        super().__init__(
            f"{stream.__class__.__name__} stuck without advancing.\n"
            f"in node: {stream.__stream__.node!r}\n"
            f"row@{stream.__stream__.row_n}: {stream.__stream__.row!r}\n"
            f"unparsed@{stream.__stream__.viewpoint + stream.__cursor__}: {stream.unparsed!r}"
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

    delimiter: NodeToken | EndToken | Token | None
    """which delimits the designated content (None for row end)"""
    designated: str
    """the designated content"""

    def __init__(
            self,
            stream: Stream,
            delimiter: NodeToken | NodeToken | None,
    ):
        """substream for tokenization"""
        self.__stream__ = stream
        self.delimiter = delimiter
        self.__seen_start__ = -1
        self.__cursor__ = 0
        self.designated = self.__stream__.row[
            slice(
                self.__stream__.viewpoint,
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

    def __tokenize__(self):
        node = self.__stream__.node
        while self.__istart__():
            self.__seen_start__ = self.__cursor__
            node.inner.append(node.phrase.tokenize(self)(
                seen_start=self.__seen_start__,
                content=self.__buffer__.getvalue(),
                stream=self.__stream__,
                node=node,
            ))


class NullTokenizeStream(TokenizeStream):

    def __tokenize__(self):
        self.__stream__.node.stack.append(
            self.__stream__.node.phrase.TToken(
                seen_start=0,
                content=self.designated,
                stream=self.__stream__,
                node=self.__stream__.node,
            )
        )


class Stream:
    rows: list[str]
    """remain unparsed rows"""
    row: str
    """current row to parse"""
    row_n: int
    """row count"""
    viewpoint: int
    """viewpoint in current row"""
    node: NodeToken
    """current active node"""

    def __init__(
            self,
            rows: list[str],
    ):
        """
        Class for processing rows and managing branches and tokens.

        The Stream class is used to process rows from a given list of strings.
        It manages the current processing position, processes branches and tokens, and manages transitions between rows.
        The class provides mechanisms for processing nested structures of branches and tokens.
        """
        self.rows = rows
        self.row_n = -1  # increment @ next line
        self.__nextrow__()

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
            self.row = self.rows.pop(0)
        except IndexError:
            raise EOFError
        else:
            self.row_n += 1
            self.viewpoint = 0

    def __carry__(self, item: Token | NodeToken):
        """carry the viewpoint to the end of a parsed token"""
        self.viewpoint += item.seen_start + item.len_token

    def __item_start__(self, item: Token | NodeToken):
        """start a node or handle stand-alone-token"""
        if item.seen_start:
            # remain token
            self.node.phrase.TTokenizeStream(self, item).__tokenize__()

        self.node.inner.append(item)

        item.__atStart__(self)

        if isinstance(item, NodeToken):
            self.node = item

        self.__carry__(item)

        if self.viewpoint >= len(self.row):
            self.__nextrow__()

    def __search_suffix__(self) -> NodeToken | None:
        """search for suffix phrase"""
        suffix_starts = list()
        for xp in self.node.phrase.__suffix_phrases__:
            # passes the parent node of the node belonging to the suffix
            # to return to it at the end of the suffix
            if suffix_node := xp.starts(self, self.node.node):
                suffix_starts.append(suffix_node)
        return min(suffix_starts) if suffix_starts else None

    def __item_stop__(self, node: EndToken):
        """end a node"""
        if node.seen_start:
            # remain token
            self.node.phrase.TTokenizeStream(self, node).__tokenize__()

        self.node.end = node  # end node

        node.__atEnd__(self)

        self.__carry__(node)

        if self.viewpoint >= len(self.row):
            self.__nextrow__()

        if suffix_start := self.__search_suffix__():
            self.__item_start__(suffix_start)
        else:
            # return to the parent node
            self.node = self.node.node

    def __search_sub__(self) -> NodeToken | Token | None:
        """search for sub phrase"""
        sub_starts = list()
        for sp in self.node.phrase.__sub_phrases__:
            if start_node := sp.starts(self, self.node):
                sub_starts.append(start_node)
        return min(sub_starts) if sub_starts else None

    def __call__(self):
        """main iteration"""
        active_stop = self.node.__ends__(self)

        if sub_start := self.__search_sub__():
            if active_stop and active_stop < sub_start:
                self.__item_stop__(active_stop)
            else:
                self.__item_start__(sub_start)
        elif active_stop:
            self.__item_stop__(active_stop)
        else:
            self.node.phrase.TTokenizeStream(self, None).__tokenize__()
            self.__nextrow__()


class Token:
    xml_label = "T"
    """xml label used in repr"""

    node: NodeToken
    """source node of the token"""
    content: str
    """content of the token"""
    row_n: int
    """row number where the token is located"""
    viewpoint: int
    """viewpoint from which the stream was searched for"""
    seen_start: int
    """starting point of the token relative to the viewpoint"""

    def __init__(
            self,
            seen_start: int,
            content: str,
            stream: Stream,
            node: NodeToken,
    ):
        """
        Represents a token extracted from a stream within a specific node.

        A `Token` object captures essential metadata about a segment of content, such as
        its position within a stream, the row and column details, its parent node, and
        methods to determine its relationships with neighboring tokens. It is used to
        model discrete units for stream parsing and processing, providing detailed
        information about its location and context.

        [*interface*] (can be used as the return value of the interface method ``Phrase.start``)

        :param seen_start: start point of the token relative to the stream.viewpoint
        :param content: content of the token
        :param stream: stream object
        :param node: parent node of the token
        """
        self.seen_start = seen_start
        self.content = content
        self.row_n = stream.row_n
        self.viewpoint = stream.viewpoint
        self.node = node

    @property
    def seen_end(self) -> int:
        """ending point of the token relative to the viewpoint"""
        return self.seen_start + len(self.content)

    @property
    def column_start(self) -> int:
        """starting point of the token relative to the whole row"""
        return self.viewpoint + self.seen_start

    @property
    def column_end(self) -> int:
        """ending point of the token relative to the whole row"""
        return self.viewpoint + self.seen_end

    @property
    def len_token(self):
        """length of the token-content"""
        return len(self.content)

    def __lt__(self, other: Token) -> bool:
        """used to determine the priority of tokens

        The token that appeared first has the highest priority.
        If several tokens are at the same position, the longest one is prioritized.
        """
        return self.seen_start < other.seen_start if self.seen_start != other.seen_start else len(self.content) > len(other.content)

    def __repr__(self):
        return f'<{self.xml_label} coord="{self.row_n}:{self.column_start}:{self.column_end}">{self.content!r}</{self.xml_label}>'

    def __str__(self):
        """return self.content"""
        return self.content

    def __atStart__(self, stream: Stream):
        """[*wrapper*]"""
        self.node.__atStart__(stream)


class EndToken(Token):
    """Type of tokens (`Token`) at the beginning and end of a node.
    """
    xml_label = "E"
        
    def __atEnd__(self, stream: Stream):
        """[*wrapper*]"""
        self.node.__atEnd__(stream)


class NodeToken(Token):
    xml_label = "N"

    phrase: Phrase

    inner: list[Token | NodeToken]
    end: EndToken

    def __init__(
            self,
            seen_start: int,
            content: str,
            stream: Stream,
            node: NodeToken,
            phrase: Phrase,
    ):
        """
        Serves as a container for tokens of the specific phrase and can contain sub- or suffix-branches.

        [*interface*] (can be used as the return value of the interface method ``Phrase.start``)

        :param seen_start: start point of the token relative to the stream.viewpoint / in stream.unparsed
        :param content: content
        :param stream: stream object
        :param node: parent node
        :param phrase: phrase object
        """
        self.phrase = phrase
        Token.__init__(self, seen_start, content, stream, node)
        self.inner = list()

    @property
    def root(self) -> RootNodeToken:
        return self.node.root

    @property
    def last_row_n(self) -> int:
        """row number where the node ends"""
        return self.end.row_n

    @property
    def len_inner(self):
        """length of the whole inner content"""
        return sum(t.len_token for t in self.gen_inner())

    @property
    def len_branch(self):
        """length of the whole inner content"""
        return self.len_token + self.len_inner + self.end.len_token

    def __ends__(self, stream: Stream) -> EndToken | None:
        """[*wrapper*]"""
        return self.phrase.ends(stream)

    def gen_inner(self) -> Generator[NodeToken | EndToken | Token, Any, None]:
        """generate inner tokens recursively"""
        for i in self.inner:
            if isinstance(i, NodeToken):
                yield i
                yield from i.gen_inner()
                yield i.end
            else:
                yield i

    def gen_branch(self) -> Generator[NodeToken | EndToken | Token, Any, None]:
        """generate node tokens recursively"""
        yield self
        yield from self.gen_inner()
        yield self.end

    def get_inner_content(self) -> str:
        """content of the inner tokens"""
        return str().join(t.content for t in self.gen_inner())

    def get_branch_content(self) -> str:
        """content of the node"""
        return self.content + self.get_inner_content() + self.end.content

    def __repr__(self):
        return f"<{self.xml_label} phrase={str(self.phrase.id)!r}>{super().__repr__()}{str().join(repr(i) for i in self.inner)}{self.end!r}</{self.xml_label}>"

    def __getitem__(self, item):
        """get inner token on index"""
        return self.inner[item]

    def __atStart__(self, stream: Stream):
        """[*wrapper*]"""
        self.phrase.atStart(stream, self)

    def __atEnd__(self, stream: Stream):
        """[*wrapper*]"""
        self.phrase.atEnd(stream, self)


class Phrase:
    id: Any
    """[*interface*] phrase id"""
    TNodeToken: Type[NodeToken] = NodeToken
    """[*interface*] node-token class"""
    TToken: Type[Token] = Token
    """[*interface*] token class"""
    TEndToken: Type[EndToken] = EndToken
    """[*interface*] end-token class"""

    TTokenizeStream: Type[TokenizeStream] = TokenizeStream
    """tokenize stream class"""

    @overload
    def __init__(
            self, *,
            id: Any = ...,
            TToken: Type[Token] = ...,
            TNodeToken: Type[NodeToken] = ...,
            TEndToken: Type[EndToken] = ...,
            TTokenizeStream: Type[TokenizeStream] = ...,
            **kwargs,
    ):
        ...

    @overload
    def __init__(self, **kwargs):
        ...

    def __init__(self, **kwargs):
        """
        Represents a phrase entity providing interfaces for tokenization, node detection,
        and managing relationships with other phrases.

        This class serves as a flexible mechanism for handling tokenization and branching logic within
        a stream. It allows the addition of phrases and suffix phrases to build complex relationships
        and supports recursive parsing functionality.

        [*interface*]

        :param kwargs: additional attributes set on the phrase object by __dict__.update
        """
        self.__dict__.update(kwargs)
        if not hasattr(self, "id"):
            self.id = id(self)
        self.__sub_phrases__ = set()
        self.__suffix_phrases__ = set()
        if self.__class__.tokenize is Phrase.tokenize:
            # saves some operations in the parsing process
            # if tokenize has not been defined
            self.TTokenizeStream = NullTokenizeStream

    def starts(self, stream: Stream, node: NodeToken) -> NodeToken | Token | None:
        """[*interface*]

        Returns a starting node or stand-alone token in the unparsed content of the current row in the stream (``stream.unparsed``).
        `node` is the parent node and is for prefix branches NOT ``stream.node``, which in this context is the source node for the prefix.

        Configuration example:

        ..code-block::

            stream.unparsed  # "foo*bar"

            try:
                i = stream.unparsed.index("*")  # 3
                return self.TNodeToken(seen_start=i, content="*", stream=stream, node=node, phrase=self)
                # If this token prevails over any other start/end/stand-alone tokens of the parent node
                # (determined by the starting point and length of the content), "foo" is added to the parent node.
            except ValueError:
                return None

        """

        return self.TNodeToken(0, stream.unparsed, stream, node, self)

    def tokenize(
            self,
            stream: TokenizeStream,
    ) -> Type[Token] | Callable[[int, str, Stream, NodeToken], Type[Token]]:
        """[*interface*]

        Allows for a dedicated allocation and typing of tokens within a node.

        When called, the method must advance the passed stream using its ``eat_*`` methods
        (which define the content of the token).
        The return value is a factory/token type that will create the token (autonomously).
        """
        ...

    def ends(self, stream: Stream) -> EndToken | None:
        """[*interface*]

        Returns a found node-end-token (``NodeToken``) in the unparsed content of the current row in the stream (``stream.unparsed``).

        Configuration example:

        ..code-block::

            stream.unparsed  # "foo*bar"

            try:
                i = stream.unparsed.index("*")  # 3
                return self.TEndToken(seen_start=i, content="*", stream=stream, node=stream.node)
                # If this token prevails over any other start/end/stand-alone tokens of the parent node
                # (determined by the starting point and length of the content), "foo" is added to the parent node.
            except ValueError:
                return None
        """
        return self.TEndToken(0, "", stream, stream.node)

    def atStart(self, stream: Stream, node: NodeToken):
        """[*interface*] additional callback when a node start is occurred and accepted"""
        ...

    def atEnd(self, stream: Stream, node: NodeToken):
        """[*interface*] additional callback when a node end is occurred and accepted"""
        ...

    __sub_phrases__: set[Phrase]
    __suffix_phrases__: set[Phrase]

    @overload
    def add_phrases(self, node: Phrase | Iterable[Phrase], *nodes: Phrase | Iterable[Phrase], mutual: bool = False) -> Self:
        ...

    @overload
    def add_phrases(self, node: Phrase | Iterable[Phrase], *nodes: Phrase | Iterable[Phrase], mutual: bool = False) -> Self:
        ...

    def add_phrases(self, *nodes: Phrase | Iterable[Phrase], mutual: bool = False) -> Self:
        """Add one or more phrases to the current phrase. This method can link
        phrases either unidirectionally or bidirectionally based on the `mutual` parameter.
        """
        if mutual:
            def _i():
                nonlocal node
                if isinstance(node, Phrase):
                    self.__sub_phrases__.add(node)
                    node.__sub_phrases__.add(self)
                else:
                    for _node in node:
                        self.__sub_phrases__.add(_node)
                        _node.__sub_phrases__.add(self)
        else:
            def _i():
                nonlocal node
                if isinstance(node, Phrase):
                    self.__sub_phrases__.add(node)
                else:
                    for _node in node:
                        self.__sub_phrases__.add(_node)

        for node in nodes:
            _i()

        return self

    def add_self(self) -> Self:
        """Add the phrase to its own sub-phrases for recursive parsing."""
        self.__sub_phrases__.add(self)
        return self

    @overload
    def add_suffix_phrases(self, node: Phrase | Iterable[Phrase], *nodes: Phrase | Iterable[Phrase]) -> Self:
        ...

    @overload
    def add_suffix_phrases(self, node: Phrase | Iterable[Phrase], *nodes: Phrase | Iterable[Phrase]) -> Self:
        ...

    def add_suffix_phrases(self, *nodes: Phrase | Iterable[Phrase]) -> Self:
        """Add one or more suffix phrases to the current phrase."""
        self.__suffix_phrases__.update(nodes)
        return self

    def add_self_suffix(self) -> Self:
        """Add the phrase to its own suffix-phrases for chained parsing."""
        self.__suffix_phrases__.add(self)
        return self

    @overload
    def rm_phrases(self, node: Phrase | Iterable[Phrase], *nodes: Phrase | Iterable[Phrase], mutual: bool = False) -> Self:
        ...

    @overload
    def rm_phrases(self, node: Phrase | Iterable[Phrase], *nodes: Phrase | Iterable[Phrase], mutual: bool = False) -> Self:
        ...

    def rm_phrases(self, *nodes: Phrase | Iterable[Phrase], mutual: bool = False) -> Self:
        """Remove one or more phrases to the current phrase. This method can unlink
        phrases either unidirectionally or bidirectionally based on the `mutual` parameter.
        """
        if mutual:
            def _i():
                nonlocal node
                if isinstance(node, Phrase):
                    self.__sub_phrases__.discard(node)
                    node.__sub_phrases__.discard(self)
                else:
                    for _node in node:
                        self.__sub_phrases__.discard(_node)
                        _node.__sub_phrases__.discard(self)
        else:
            def _i():
                nonlocal node
                if isinstance(node, Phrase):
                    self.__sub_phrases__.discard(node)
                else:
                    for _node in node:
                        self.__sub_phrases__.discard(_node)

        for node in nodes:
            _i()

        return self

    def rm_self(self) -> Self:
        """Remove the phrase from its own sub-phrases."""
        self.__sub_phrases__.discard(self)
        return self

    @overload
    def rm_suffix_phrases(self, node: Phrase | Iterable[Phrase], *nodes: Phrase | Iterable[Phrase]) -> Self:
        ...

    @overload
    def rm_suffix_phrases(self, node: Phrase | Iterable[Phrase], *nodes: Phrase | Iterable[Phrase]) -> Self:
        ...

    def rm_suffix_phrases(self, *nodes: Phrase | Iterable[Phrase]) -> Self:
        """Remove one or more suffix phrases from the current phrase."""
        self.__suffix_phrases__ -= set(nodes)
        return self

    def rm_self_suffix(self) -> Self:
        """Remove the phrase from its own suffix-phrases."""
        self.__suffix_phrases__.discard(self)
        return self

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {str(self.id)!r}>"


class DefaultToken(Token):
    xml_label = "D"


class EOFToken(EndToken):
    xml_label = "EOF"


class RootNodeToken(NodeToken):
    xml_label = "R"

    phrase: MainPhrase

    inner: list[DefaultToken | NodeToken]
    end: EOFToken

    @property
    def root(self) -> Self:
        return self

    def __ends__(self, stream: Stream) -> NodeToken | None:
        return None

    def __lt__(self, other: NodeToken) -> bool:
        pass

    def __init__(self, phrase: MainPhrase, stream: Stream):
        NodeToken.__init__(self, 0, "", stream, self, phrase)


class MainPhrase(Phrase):
    TRootNodeToken: Type[RootNodeToken] = RootNodeToken
    """[*interface*] root-node class"""
    TEndToken: Type[EOFToken] = EOFToken
    """[*interface*] EOF-token class"""
    TToken: Type[DefaultToken] = DefaultToken
    """[*interface*] default-token class"""
    TStream: Type[Stream] = Stream
    """[*interface*] stream class"""

    def starts(self, *_, **__) -> None:
        raise RuntimeError

    def parse_rows(self, rows: list[str]) -> RootNodeToken:
        """parse rows

        **Line breaks must be explicitly defined in rows! Otherwise, they will not be recognized during the parsing process.**
        """
        if not rows:
            raise EOFError
        stream = self.TStream(rows)
        root = self.TRootNodeToken(self, stream)
        stream.node = root
        try:
            while True:
                stream()
        except EOFError:
            root.end = self.TEndToken(
                root[-1].seen_end,
                "",
                stream,
                root
            )
            root.end.__atEnd__(stream)
            return root

    def parse_string(self, string: str) -> RootNodeToken:
        """parse string"""
        return self.parse_rows(string.splitlines(keepends=True))
