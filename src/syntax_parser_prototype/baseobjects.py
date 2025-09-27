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
            f"in branch: {stream.__stream__.branch!r}\n"
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

    delimiter: Token | NodeToken | TokenBranch | None
    """which delimits the designated content (None for row end)"""
    designated: str
    """the designated content"""

    def __init__(
            self,
            stream: Stream,
            delimiter: NodeToken | TokenBranch | None,
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
        branch = self.__stream__.branch
        while self.__istart__():
            self.__seen_start__ = self.__cursor__
            branch.stack.append(branch.phrase.tokenize(self)(
                seen_start=self.__seen_start__,
                content=self.__buffer__.getvalue(),
                stream=self.__stream__,
                branch=branch,
            ))


class NullTokenizeStream(TokenizeStream):

    def __tokenize__(self):
        self.__stream__.branch.stack.append(
            self.__stream__.branch.phrase.TToken(
                seen_start=0,
                content=self.designated,
                stream=self.__stream__,
                branch=self.__stream__.branch,
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
    branch: TokenBranch
    """current active branch"""

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

    def __carry__(self, item: Token | TokenBranch):
        """carry the viewpoint to the end of a parsed token"""
        self.viewpoint += item.seen_start + item.len_token

    def __item_start__(self, item: Token | TokenBranch):
        """start a branch or handle stand-alone-token"""
        if item.seen_start:
            # remain token
            self.branch.phrase.TTokenizeStream(self, item).__tokenize__()

        self.branch.stack.append(item)

        item.__atStart__(self)

        if isinstance(item, TokenBranch):
            self.branch = item

        self.__carry__(item)

        if self.viewpoint >= len(self.row):
            self.__nextrow__()

    def __search_suffix__(self) -> TokenBranch | None:
        """search for suffix phrase"""
        suffix_starts = list()
        for xp in self.branch.phrase.__suffix_phrases__:
            # passes the parent branch of the branch belonging to the suffix
            # to return to it at the end of the suffix
            if suffix_node := xp.starts(self, self.branch.branch):
                suffix_starts.append(suffix_node)
        return min(suffix_starts) if suffix_starts else None

    def __item_stop__(self, node: NodeToken):
        """end a branch"""
        if node.seen_start:
            # remain token
            self.branch.phrase.TTokenizeStream(self, node).__tokenize__()

        self.branch.stack.append(node)  # end node

        node.__atEnd__(self)

        self.__carry__(node)

        if self.viewpoint >= len(self.row):
            self.__nextrow__()

        if suffix_start := self.__search_suffix__():
            self.__item_start__(suffix_start)
        else:
            # return to the parent branch
            self.branch = self.branch.branch

    def __search_sub__(self) -> TokenBranch | Token | None:
        """search for sub phrase"""
        sub_starts = list()
        for sp in self.branch.phrase.__sub_phrases__:
            if start_node := sp.starts(self, self.branch):
                sub_starts.append(start_node)
        return min(sub_starts) if sub_starts else None

    def __call__(self):
        """main iteration"""
        active_stop = self.branch.__ends__(self)

        if sub_start := self.__search_sub__():
            if active_stop and active_stop < sub_start:
                self.__item_stop__(active_stop)
            else:
                self.__item_start__(sub_start)
        elif active_stop:
            self.__item_stop__(active_stop)
        else:
            self.branch.phrase.TTokenizeStream(self, None).__tokenize__()
            self.__nextrow__()


class Token:
    xml_label = "T"
    """xml label used in repr"""

    branch: TokenBranch
    """source branch of the token"""
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
            branch: TokenBranch,
    ):
        """
        Represents a token extracted from a stream within a specific branch.

        A `Token` object captures essential metadata about a segment of content, such as
        its position within a stream, the row and column details, its parent branch, and
        methods to determine its relationships with neighboring tokens. It is used to
        model discrete units for stream parsing and processing, providing detailed
        information about its location and context.

        [*interface*] (can be used as the return value of the interface method ``Phrase.start``)

        :param seen_start: start point of the token relative to the stream.viewpoint
        :param content: content of the token
        :param stream: stream object
        :param branch: parent branch of the token
        """
        self.seen_start = seen_start
        self.content = content
        self.row_n = stream.row_n
        self.viewpoint = stream.viewpoint
        self.branch = branch

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
    def index_in_branch(self) -> int:
        """index of the token in the branch stack"""
        return self.branch.stack.index(self)

    @property
    def right_neighbor(self) -> Token | NodeToken | TokenBranch:
        """right neighbor-token"""
        if self.index_in_branch == len(self.branch.stack) - 1:
            return self.branch.right_neighbor
        else:
            return self.branch[self.index_in_branch + 1]

    @property
    def left_neighbor(self) -> Token | NodeToken | TokenBranch:
        """left neighbor-token"""
        if self.index_in_branch == 0:
            return self.branch.left_neighbor
        else:
            return self.branch[self.index_in_branch - 1]

    @property
    def len_token(self):
        """length of the token-content"""
        return len(self.content)

    @property
    def is_start_node(self) -> bool:
        """whether the token is the start-node"""
        return self is self.branch.start_node

    @property
    def is_end_node(self) -> bool:
        """whether the token is the end-node"""
        return self is self.branch.end_node

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
        self.branch.__atStart__(stream)


class NodeToken(Token):
    """Type of tokens (`Token`) at the beginning and end of a branch.
    """
    xml_label = "N"

    def __atEnd__(self, stream: Stream):
        """[*wrapper*]"""
        self.branch.__atEnd__(stream)


class TokenBranch(Token):
    xml_label = "B"

    phrase: Phrase
    stack: list[NodeToken | Token | TokenBranch | NodeToken]

    def __init__(
            self,
            seen_start: int,
            content: str,
            stream: Stream,
            branch: TokenBranch,
            phrase: Phrase,
    ):
        """
        Serves as a container for tokens of the specific phrase and can contain sub- or suffix-branches.

        [*interface*] (can be used as the return value of the interface method ``Phrase.start``)

        :param seen_start: start point of the token relative to the stream.viewpoint / in stream.unparsed
        :param content: content
        :param stream: stream object
        :param branch: parent branch
        :param phrase: phrase object
        """
        Token.__init__(self, seen_start, '', stream, branch)
        self.phrase = phrase
        self.stack = [self.phrase.TNodeToken(self.seen_start, content, stream, branch=self)]

    @property
    def last_row_n(self) -> int:
        """row number where the branch ends"""
        return self.end_node.row_n

    @property
    def root(self) -> RootPhrase:
        """root phrase"""
        return self.branch.root

    @property
    def start_node(self) -> NodeToken:
        """first node in the branch"""
        return self[0]

    @property
    def end_node(self) -> NodeToken:
        """last node in the branch"""
        return self[-1]

    @property
    def len_inner(self):
        """length of the whole inner content"""
        return sum(t.len_token for t in self.gen_inner())

    @property
    def len_token(self):
        """length of the start-node-content"""
        return self.start_node.len_token

    def __ends__(self, stream: Stream) -> NodeToken | None:
        """[*wrapper*]"""
        return self.phrase.ends(stream)

    def gen_inner(self) -> Generator[Token, Any, None]:
        """generate inner tokens recursively"""
        for i in self.stack:
            if isinstance(i, TokenBranch):
                yield from i.gen_inner()
            else:
                yield i

    def get_inner_content(self) -> str:
        """content of the token branch"""
        return str().join(t.content for t in self.gen_inner())

    def __repr__(self):
        return f"<{self.xml_label} phrase={str(self.phrase.id)!r}>{str().join(repr(i) for i in self.stack)}</{self.xml_label}>"

    def __getitem__(self, item):
        """get token on index"""
        return self.stack[item]

    def __atStart__(self, stream: Stream):
        """[*wrapper*]"""
        self.phrase.atStart(stream, self)

    def __atEnd__(self, stream: Stream):
        """[*wrapper*]"""
        self.phrase.atEnd(stream, self)


class Phrase:
    id: Any
    """[*interface*] phrase id"""
    TToken: Type[Token] = Token
    """[*interface*] token class"""
    TNodeToken: Type[NodeToken] = NodeToken
    """[*interface*] node-token class"""
    TTokenBranch: Type[TokenBranch] = TokenBranch
    """[*interface*] branch class"""

    TTokenizeStream: Type[TokenizeStream] = TokenizeStream
    """tokenize stream class"""

    @overload
    def __init__(
            self, *,
            id: Any = ...,
            TToken: Type[Token] = ...,
            TNodeToken: Type[NodeToken] = ...,
            TBranch: Type[TokenBranch] = ...,
            TTokenizeStream: Type[TokenizeStream] = ...,
            **kwargs,
    ):
        ...

    @overload
    def __init__(self, **kwargs):
        ...

    def __init__(self, **kwargs):
        """
        Represents a phrase entity providing interfaces for tokenization, branch detection,
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

    def starts(self, stream: Stream, branch: TokenBranch) -> TokenBranch | Token | None:
        """[*interface*]

        Returns a starting branch or stand-alone token in the unparsed content of the current row in the stream (``stream.unparsed``).
        `branch` is the parent branch and is for prefix branches NOT ``stream.branch``, which in this context is the source branch for the prefix.

        Configuration example:

        ..code-block::

            stream.unparsed  # "foo*bar"

            try:
                i = stream.unparsed.index("*")  # 3
                return self.TTokenBranch(seen_start=i, content="*", stream=stream, branch=branch, phrase=self)
                # If this token prevails over any other start/end/stand-alone tokens of the parent branch
                # (determined by the starting point and length of the content), "foo" is added to the parent branch.
            except ValueError:
                return None

        """

        return self.TTokenBranch(0, stream.unparsed, stream, branch, self)

    def tokenize(
            self,
            stream: TokenizeStream,
    ) -> Type[Token] | Callable[[int, str, Stream, TokenBranch], Type[Token]]:
        """[*interface*]

        Allows for a dedicated allocation and typing of tokens within a branch.

        When called, the method must advance the passed stream using its ``eat_*`` methods
        (which define the content of the token).
        The return value is a factory/token type that will create the token (autonomously).
        """
        ...

    def ends(self, stream: Stream) -> NodeToken | None:
        """[*interface*]

        Returns a found branch-end-token (``NodeToken``) in the unparsed content of the current row in the stream (``stream.unparsed``).

        Configuration example:

        ..code-block::

            stream.unparsed  # "foo*bar"

            try:
                i = stream.unparsed.index("*")  # 3
                return self.TNodeToken(seen_start=i, content="*", stream=stream, branch=stream.branch)
                # If this token prevails over any other start/end/stand-alone tokens of the parent branch
                # (determined by the starting point and length of the content), "foo" is added to the parent branch.
            except ValueError:
                return None
        """
        return self.TNodeToken(0, "", stream, stream.branch)

    def atStart(self, stream: Stream, branch: TokenBranch):
        """[*interface*] additional callback when a branch start is occurred and accepted"""
        ...

    def atEnd(self, stream: Stream, branch: TokenBranch):
        """[*interface*] additional callback when a branch end is occurred and accepted"""
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


class RootToken(Token):
    xml_label = "RT"


class RootNodeToken(NodeToken):
    xml_label = "RN"


class RootTokenBranch(TokenBranch):
    xml_label = "RB"

    @property
    def root(self) -> RootPhrase:
        return self.phrase

    def __ends__(self, stream: Stream) -> NodeToken | None:
        return None

    def __lt__(self, other: TokenBranch) -> bool:
        pass

    def __init__(self, root_phrase: RootPhrase):
        self.phrase = root_phrase
        TokenBranch.__init__(self, 0, "", root_phrase.stream, self, root_phrase)

    def __drop_after__(self, token: Token):
        self.stack = self.stack[:self.stack.index(token) + 1]


class RootPhrase(Phrase):
    TRootBranch: Type[RootTokenBranch] = RootTokenBranch
    """[*interface*] root-branch class"""
    TNodeToken: Type[RootNodeToken] = RootNodeToken
    """[*interface*] root-node-token class"""
    TToken: Type[RootToken] = RootToken
    """[*interface*] root-token class"""
    TStream: Type[Stream] = Stream
    """[*interface*] stream class"""

    branch: RootTokenBranch
    stream: Stream

    def __init__(self, **kwargs):
        Phrase.__init__(self, **kwargs)
        self.root = self

    def starts(self, *_, **__) -> None:
        raise RuntimeError

    def parse_rows(self, rows: list[str]) -> RootTokenBranch:
        """parse rows

        **Line breaks must be explicitly defined in rows! Otherwise, they will not be recognized during the parsing process.**
        """
        if not rows:
            raise EOFError
        self.stream = self.TStream(rows)
        self.branch = self.TRootBranch(self)
        self.stream.branch = self.branch
        try:
            while True:
                self.stream()
        except EOFError:
            self.branch.stack.append(
                en := self.branch.phrase.TNodeToken(
                    self.branch[-1].seen_end,
                    "",
                    self.stream,
                    self.branch
                )
            )
            en.__atEnd__(self.stream)
            return self.branch

    def parse_string(self, string: str) -> RootTokenBranch:
        """parse string"""
        return self.parse_rows(string.splitlines(keepends=True))
