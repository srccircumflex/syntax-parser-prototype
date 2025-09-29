from __future__ import annotations

from collections.abc import Iterable
from typing import Any, overload, TYPE_CHECKING, Type, Callable

if TYPE_CHECKING:
    from typing_extensions import Self

from .streams import (
    TokenizeStream,
    NullTokenizeStream,
    Stream,
)
from .tokens import (
    Token,
    NodeToken,
    MaskToken,
    MaskNodeToken,
    EndToken,
    OpenEndToken,
    DefaultToken,
    EOFToken,
    RootNodeToken,
)


__all__ = (
    "Phrase",
    "MainPhrase"
)


class Phrase:
    id: Any
    """[*interface*] phrase id"""
    TNullToken: Type[Token] = Token
    """[*interface*] default token class (used if tokenize is not defined)"""
    TOpenEndToken: Type[OpenEndToken] = OpenEndToken
    """[*interface*] initial end-token class"""

    TTokenizeStream: Type[TokenizeStream] = TokenizeStream
    """[*interface*] tokenize stream class"""
    TNullTokenizeStream: Type[NullTokenizeStream] = NullTokenizeStream
    """[*interface*] null-tokenize stream class"""

    @overload
    def __init__(
            self, *,
            id: Any = ...,
            TDefaultToken: Type[Token] = ...,
            TOpenEndToken: Type[OpenEndToken] = ...,
            TTokenizeStream: Type[TokenizeStream] = ...,
            TNullTokenizeStream: Type[NullTokenizeStream] = ...,
            **kwargs,
    ):
        ...

    @overload
    def __init__(self, **kwargs):
        ...

    def __init__(self, **kwargs):
        """[*interface*]

        Represents a phrase entity providing interfaces for tokenization, node detection,
        and managing relationships with other phrases.

        This class serves as a flexible mechanism for handling tokenization and branching logic within
        a stream. It allows the addition of phrases and suffix phrases to build complex relationships
        and supports recursive parsing functionality.

        *[ i ]* If ``start`` returns a ``MaskToken``, sub-/suffix-phrases are **NOT** evaluated.

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
            self.TTokenizeStream = self.TNullTokenizeStream

    def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
        """[*interface*]

        Returns a starting node or stand-alone token in the unparsed content of the current row in the stream (``stream.unparsed``).

        Configuration example:

        ..code-block::

            stream.unparsed  # "foo*bar"

            try:
                i = stream.unparsed.index("*")  # 3
                return NodeToken(seen_start=i, content="*")
                # If this token prevails over any other start/end/stand-alone tokens of the parent node
                # (determined by the starting point and length of the content), "foo" is added to the parent node.
            except ValueError:
                return None

        """
        return NodeToken(0, stream.unparsed)

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
                return EndToken(seen_start=i, content="*")
                # If this token prevails over any other start/end/stand-alone tokens of the parent node
                # (determined by the starting point and length of the content), "foo" is added to the parent node.
            except ValueError:
                return None
        """
        return EndToken(0, "")

    def atStart(self, stream: Stream, node: NodeToken | MaskNodeToken):
        """[*interface*] additional callback when a node start is occurred and accepted"""
        ...

    def atEnd(self, stream: Stream, node: NodeToken | MaskNodeToken):
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
        """Add the phrase to its own sub-phrases for recursive parsing.

        *[ i ]* If ``start`` returns a ``MaskToken``, subphrases are **NOT** evaluated.
        """
        self.__sub_phrases__.add(self)
        return self

    @overload
    def add_suffix_phrases(self, node: Phrase | Iterable[Phrase], *nodes: Phrase | Iterable[Phrase]) -> Self:
        ...

    @overload
    def add_suffix_phrases(self, node: Phrase | Iterable[Phrase], *nodes: Phrase | Iterable[Phrase]) -> Self:
        ...

    def add_suffix_phrases(self, *nodes: Phrase | Iterable[Phrase]) -> Self:
        """Add one or more suffix phrases to the current phrase.

        *[ i ]* If ``start`` returns a ``MaskToken``, subphrases are **NOT** evaluated.
        """
        self.__suffix_phrases__.update(nodes)
        return self

    def add_self_suffix(self) -> Self:
        """Add the phrase to its own suffix-phrases for chained parsing.

        *[ i ]* If ``start`` returns a ``MaskToken``, subphrases are **NOT** evaluated.
        """
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


class MainPhrase(Phrase):
    TRootNodeToken: Type[RootNodeToken] = RootNodeToken
    """[*interface*] root-node class"""
    TEOFToken: Type[EOFToken] = EOFToken
    """[*interface*] EOF-token class"""
    TToken: Type[DefaultToken] = DefaultToken
    """[*interface*] default-token class"""
    TStream: Type[Stream] = Stream
    """[*interface*] stream class"""

    @overload
    def __init__(
            self, *,
            id: Any = ...,
            TToken: Type[DefaultToken] = ...,
            TRootNodeToken: Type[RootNodeToken] = ...,
            TEOFToken: Type[EOFToken] = ...,
            TStream: Type[Stream] = ...,
            **kwargs,
    ):
        ...

    @overload
    def __init__(self, **kwargs):
        ...

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def starts(self, *_, **__) -> None:
        raise RuntimeError

    def parse_rows(self, rows: list[str]) -> RootNodeToken:
        """parse rows

        **Line breaks must be explicitly defined in rows!
        Otherwise, they will not be recognized during the parsing process.**
        """
        if not rows:
            raise ValueError("rows must not be empty")
        root = self.TRootNodeToken(self)
        stream = self.TStream(
            rows.pop(0),
            rows,
            root,
        )
        stream.__run__()
        root.end = self.TEOFToken(root)
        root.end.__atEnd__(stream)
        return root

    def parse_string(self, string: str) -> RootNodeToken:
        """parse string"""
        return self.parse_rows(string.splitlines(keepends=True))
