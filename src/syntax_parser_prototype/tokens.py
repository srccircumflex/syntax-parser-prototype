from __future__ import annotations

from typing import TYPE_CHECKING, Generator, Any

if TYPE_CHECKING:
    from typing_extensions import Self
    from .phrases import *
    from .streams import *

__all__ = (
    "Token",
    "NodeToken",
    "MaskToken",
    "MaskNodeToken",
    "EndToken",
    "OpenEndToken",
    "DefaultToken",
    "EOFToken",
    "RootNodeToken",
)


class Token:
    xml_label = "T"
    """xml label used in repr and other visualisation for debugging"""

    seen_start: int
    """starting point of the token relative to the viewpoint"""
    content: str
    """content of the token"""
    node: NodeToken
    """source node of the token"""
    row_no: int
    """row number where the token is located"""
    viewpoint: int
    """viewpoint from which the stream was searched for"""

    def __init__(
            self,
            seen_start: int,
            content: str,
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
        """
        self.seen_start = seen_start
        self.content = content

    def __ini__(
            self,
            node: NodeToken,
            row_no: int,
            viewpoint: int
    ) -> Self:
        """late bindings"""
        self.node = node
        self.row_no = row_no
        self.viewpoint = viewpoint
        return self

    def __ini_as_token__(self, stream: Stream) -> Self:
        """late bindings for plain tokens"""
        return self.__ini__(stream.node, stream.row_no, stream.viewpoint)

    def __ini_as_node__(self, stream: Stream, phrase: Phrase) -> Self:
        """late bindings for node tokens"""
        return self.__ini__(stream.node, stream.row_no, stream.viewpoint)

    def __ini_as_suffix__(self, stream: Stream, phrase: Phrase) -> Self:
        """late bindings for suffix tokens"""
        # passes the parent node of the node belonging to the suffix
        # to return to it at the end of the suffix
        return self.__ini__(stream.node.node, stream.row_no, stream.viewpoint)

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
    def abs_start(self) -> int:
        return sum(t.len_token for t in self.gen_therebefore())

    @property
    def abs_end(self) -> int:
        return self.abs_start + self.len_token

    @property
    def len_token(self):
        """length of the token-content"""
        return len(self.content)

    @property
    def inner_index(self):
        return self.node.inner.index(self)

    @property
    def previous(self):
        if i := self.inner_index:
            return self.node[i - 1]
        else:
            return self.node

    @property
    def next(self):
        if (i := self.inner_index + 1) < len(self.node.inner):
            return self.node[i]
        else:
            return self.node.end

    def gen_thereafter(self):
        i = self.inner_index + 1
        for node in self.node.gen_path():
            yield from node.gen_inner_from_index(i)
            yield node.end
            i = node.inner_index + 1

    def gen_therebefore(self):
        i = self.inner_index
        for node in self.node.gen_path():
            yield from node.gen_reverse_inner_until_index(i)
            yield node
            i = node.inner_index

    def replace_content(self, content: str, reindex: bool = True):
        if reindex:
            diff = len(content) - self.len_token
            for t in self.gen_thereafter():
                if t.row_no != self.row_no:
                    break
                t.viewpoint += diff
        self.content = content

    def __lt__(self, other: Token) -> bool:
        """used to determine the priority of tokens

        The token that appeared first has the highest priority.
        If several tokens are at the same position, the longest one is prioritized.
        """
        return self.seen_start < other.seen_start if self.seen_start != other.seen_start else len(self.content) > len(other.content)

    def __repr__(self):
        return f'<{self.xml_label} coord="{self.row_no}:{self.column_start}:{self.column_end}">{self.content!r}</{self.xml_label}>'

    def __str__(self):
        """return self.content"""
        return self.content

    def __atStart__(self, stream: Stream):
        """[*wrapper*]"""
        self.node.__atStart__(stream)


class NodeToken(Token):
    xml_label = "N"

    phrase: Phrase

    inner: list[Token | NodeToken]
    end: EndToken | OpenEndToken

    def __init__(
            self,
            seen_start: int,
            content: str,
    ):
        """
        Serves as a container for tokens of the specific phrase and can contain sub- or suffix-branches.

        [*interface*] (can be used as the return value of the interface method ``Phrase.start``)

        :param seen_start: start point of the token relative to the stream.viewpoint / in stream.unparsed
        :param content: content
        """
        Token.__init__(self, seen_start, content)

    def __ini__(self, node: NodeToken, row_no: int, viewpoint: int, phrase: Phrase) -> Self:  # noqa: signature-differs
        self.phrase = phrase
        self.inner = list()
        self.end = phrase.TOpenEndToken(self)
        return super().__ini__(node, row_no, viewpoint)

    def __ini_as_token__(self, stream: Stream) -> Self:
        raise TypeError("NodeToken cannot be used as a plain Token")

    def __ini_as_node__(self, stream: Stream, phrase: Phrase) -> Self:
        return self.__ini__(stream.node, stream.row_no, stream.viewpoint, phrase)

    def __ini_as_suffix__(self, stream: Stream, phrase: Phrase) -> Self:
        return self.__ini__(stream.node.node, stream.row_no, stream.viewpoint, phrase)

    @property
    def root(self) -> RootNodeToken:
        return self.node.root

    def gen_path(self):
        yield self
        yield from self.node.gen_path()

    @property
    def len_inner(self):
        """length of the whole inner content"""
        return sum(t.len_token for t in self.gen_inner())

    @property
    def len_branch(self):
        """length of the branch content"""
        return self.len_token + self.len_inner + self.end.len_token

    @property
    def previous(self):
        if i := self.inner_index:
            return self.node[i - 1]
        else:
            return self.node

    @property
    def next(self):
        if self.inner:
            return self[0]
        else:
            return self.end

    def __ends__(self, stream: Stream) -> EndToken | None:
        """[*wrapper*]"""
        return self.phrase.ends(stream)

    def gen_inner(self) -> Generator[NodeToken | EndToken | OpenEndToken | Token, Any, None]:
        """generate inner tokens recursively"""
        for t in self.inner:
            if isinstance(t, NodeToken):
                yield t
                yield from t.gen_inner()
                yield t.end
            else:
                yield t

    def gen_reverse_inner(self) -> Generator[NodeToken | EndToken | OpenEndToken | Token, Any, None]:
        """generate inner tokens recursively"""
        for t in reversed(self.inner):
            if isinstance(t, NodeToken):
                yield t.end
                yield from t.gen_reverse_inner()
                yield t
            else:
                yield t

    def gen_inner_from_index(self, i: int):
        for t in self.inner[i:]:
            if isinstance(i, NodeToken):
                yield t
                yield from t.gen_inner()
                yield t.end
            else:
                yield t

    def gen_reverse_inner_until_index(self, i: int):
        for t in reversed(self.inner[:i]):
            if isinstance(t, NodeToken):
                yield t.end
                yield from t.gen_reverse_inner()
                yield t
            else:
                yield t

    def gen_branch(self) -> Generator[NodeToken | EndToken | OpenEndToken | Token, Any, None]:
        """generate inner tokens recursively with this and this end"""
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


class MaskToken(Token):

    def __init__(self, seen_start: int, content: str):
        super().__init__(seen_start, content)


class MaskNodeToken(MaskToken, NodeToken):

    def __init__(self, seen_start: int, content: str):
        MaskToken.__init__(self, seen_start, content)


class EndToken(Token):
    """Type of tokens (`Token`) at the end of a branch.
    """
    xml_label = "E"

    @property
    def previous(self):
        if self.node.inner:
            return self.node[-1]
        else:
            return self.node

    @property
    def next(self):
        if (i := self.node.inner_index + 1) < len(self.node.node.inner):
            return self.node.node[i]
        else:
            return self.node.node.end

    def __atEnd__(self, stream: Stream):
        """[*wrapper*]"""
        self.node.__atEnd__(stream)


class OpenEndToken(Token):
    """initial EndToken"""
    xml_label = "O"

    @property
    def previous(self):
        if self.node.inner:
            return self.node[-1]
        else:
            return self.node

    @property
    def next(self):
        raise EOFError

    def gen_thereafter(self):
        raise StopIteration

    @property
    def last_token(self):
        if self.node.inner:
            return self.node[-1]
        else:
            return self.node

    @property
    def seen_start(self):
        return self.last_token.seen_end

    @property
    def viewpoint(self):
        return self.last_token.viewpoint

    @property
    def row_no(self):
        return self.last_token.row_no

    def __init__(self, node: NodeToken):  # noqa: super-init-not-called
        self.content = ""
        self.node = node

    def __atEnd__(self, stream: Stream):
        """noop"""
        pass


class DefaultToken(Token):
    xml_label = "D"


class EOFToken(EndToken):
    xml_label = "EOF"

    def __init__(self, root: RootNodeToken):
        last = root[-1] if root.inner else root
        Token.__init__(self, last.seen_end, "")
        self.__ini__(root, last.row_no, last.viewpoint)

    def gen_thereafter(self):
        raise StopIteration

    @property
    def next(self):
        raise EOFError


class RootNodeToken(NodeToken):
    xml_label = "R"

    phrase: MainPhrase

    inner: list[DefaultToken | NodeToken]
    end: EOFToken

    @property
    def root(self) -> Self:
        return self

    def gen_path(self):
        yield self

    def gen_therebefore(self):
        raise StopIteration

    def __ends__(self, stream: Stream) -> NodeToken | None:
        return None

    def __lt__(self, other: NodeToken) -> bool:
        pass

    def __init__(self, phrase: MainPhrase):
        super().__init__(0, "")
        self.__ini__(self, 0, 0, phrase)
