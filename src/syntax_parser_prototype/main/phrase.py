from __future__ import annotations

from typing import overload, TYPE_CHECKING, Type, final, Iterable, Any, Callable

if TYPE_CHECKING:
    from typing_extensions import Self

from ..features import indices
from . import tokens, streams


__all__ = (
    "Phrase",
    "Root",
)


class Phrase:
    """Represents a phrase entity providing interfaces for tokenization, node detection,
    and managing relationships with other phrases.

    This class serves as a flexible mechanism for handling tokenization and branching logic
    within a stream. It allows the addition of phrases and suffix phrases to build complex
    relationships and supports recursive parsing functionality.

    **Note**
        If ``start`` returns a ``MaskToken``, sub-/suffix-phrases are **NOT** evaluated.
    """

    id: Any
    """[*ENTRY*] phrase id (memory loc id if not defined in derivatives) (default usage: only for debugging)"""
    TDefaultToken: Type[tokens.Token] = tokens.Token
    """[*ENTRY*] default token class (default usage: if tokenize is not defined)"""
    TOpenEndToken: Type[tokens.OpenEndToken] = tokens.OpenEndToken
    """[*ENTRY*] initial end-token class"""
    TTokenizeStream: Type[streams.TokenizeStream] = streams.TokenizeStream
    """[*ENTRY*] tokenize stream class"""
    TDefaultTokenizeStream: Type[streams.DefaultTokenizeStream] = streams.DefaultTokenizeStream
    """[*ENTRY*] non-tokenize stream class (if tokenize is not defined)"""

    __sub_phrases__: set[Phrase]
    __suffix_phrases__: set[Phrase]

    def __init__(self, *args, **kwargs):
        for attr in self.__annotations__:
            if attr in kwargs:
                setattr(self, attr, kwargs.pop(attr))
        if not hasattr(self, "id"):
            self.id = id(self)
        if self.__class__.tokenize is Phrase.tokenize:
            # saves some operations in the parsing process
            # if tokenize has not been defined
            self.TTokenizeStream = self.TDefaultTokenizeStream
        self.__sub_phrases__ = set()
        self.__suffix_phrases__ = set()

    def __call__(self, *args, **kwargs):
        """Creates a new instance of the class and copies the phrase configurations.
        Allows dynamic phrase definition during the parsing process.
        """
        new = self.__class__(**kwargs)
        new.__sub_phrases__ = self.__sub_phrases__.copy()
        new.__suffix_phrases__ = self.__suffix_phrases__.copy()
        return new

    def starts(self, stream: streams.Stream) -> (
            None
            | tokens.NodeToken
            | tokens.Token
            | tokens.MaskToken
            | tokens.MaskNodeToken
            | tokens.InstantToken
            | tokens.InstantNodeToken
    ):
        """[*ENTRY*]

        Must return a potential node, standalone, or masking token
        in the unparsed content of the current row (``stream.unparsed``)
        or None if the phrase does not apply.

        The following parsing behavior depends on the returned token type [and its configuration]
        (see the respective token documentation for further information).

        **Note**
            If ``start`` returns a ``MaskToken``, sub-/suffix-phrases are **NOT** evaluated.

        **Configuration example**::

            stream.unparsed  # "foo*bar!foo?"

            try:
                return NodeToken(
                    at=stream.unparsed.index("*"),  # 3
                    content="*",
                )
            except ValueError:
                return None
        """
        return tokens.NodeToken(0, len(stream.unparsed))

    def tokenize(
            self,
            stream: streams.TokenizeStream,
    ) -> Type[tokens.Token] | Callable[[int, str], tokens.Token]:
        """[*ENTRY*]

        Allows for a dedicated allocation and typing of tokens within a node.

        When called, the method must advance the passed stream using its ``eat_*`` methods
        (which define the content of the token).
        The return value is a factory/token type that will create the token (internally).

        **Configuration example**::

            stream.designated  # "bar!foo"

            if stream.eat_until(re.compile("!")):
                return FooBarToken
            else:
                stream.eat_n(1)
                return ExclToken
        """
        ...

    def ends(self, stream: streams.Stream) -> (
            None
            | tokens.EndToken
            | tokens.InstantEndToken
    ):
        """[*ENTRY*]

        Must return a potential end token of the current node
        in the unparsed content of the current row (``stream.unparsed``)
        or None if the phrase does not end.

        The following parsing behavior depends on the returned token type [and its configuration]
        (see the respective token documentation for further information).

        **Configuration example**::

            stream.unparsed  # "bar!foo?"

            try:
                return EndToken(
                    at=stream.unparsed.index("?"),  # 7
                    content="?",
                )
            except ValueError:
                return None
        """
        return tokens.InstantEndToken()

    @overload
    def add_subs(self, node: Phrase | Iterable[Phrase], *nodes: Phrase | Iterable[Phrase], mutual: bool = False) -> Self:
        ...

    @overload
    def add_subs(self, node: Phrase | Iterable[Phrase], *nodes: Phrase | Iterable[Phrase], mutual: bool = False) -> Self:
        ...

    def add_subs(self, *nodes: Phrase | Iterable[Phrase], mutual: bool = False) -> Self:
        """Add one or more sub phrases to the current phrase. This method can link
        phrases either unidirectionally or bidirectionally based on the `mutual` parameter.

        When collections are passed as iterables of phrase objects, they are unpacked internally.

        **Note**
            If ``start`` returns a ``MaskToken``, sub-/suffix-phrases are **NOT** evaluated.
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

    @overload
    def rm_subs(self, node: Phrase | Iterable[Phrase], *nodes: Phrase | Iterable[Phrase], mutual: bool = False) -> Self:
        ...

    @overload
    def rm_subs(self, node: Phrase | Iterable[Phrase], *nodes: Phrase | Iterable[Phrase], mutual: bool = False) -> Self:
        ...

    def rm_subs(self, *nodes: Phrase | Iterable[Phrase], mutual: bool = False) -> Self:
        """Remove one or more phrases from the current phrase. This method can unlink
        phrases either unidirectionally or bidirectionally based on the `mutual` parameter.

        When collections are passed as iterables of phrase objects, they are unpacked internally.
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

    def add_sub_recursion(self) -> Self:
        """Add the phrase to its own sub-phrases for recursive parsing.

        **Note**
            If ``start`` returns a ``MaskToken``, sub-/suffix-phrases are **NOT** evaluated.
        """
        self.__sub_phrases__.add(self)
        return self

    @overload
    def add_suffixes(self, node: Phrase | Iterable[Phrase], *nodes: Phrase | Iterable[Phrase]) -> Self:
        ...

    @overload
    def add_suffixes(self, node: Phrase | Iterable[Phrase], *nodes: Phrase | Iterable[Phrase]) -> Self:
        ...

    def add_suffixes(self, *nodes: Phrase | Iterable[Phrase]) -> Self:
        """Add one or more suffix phrases to the current phrase.

        When collections are passed as iterables of phrase objects, they are unpacked internally.

        Suffix phrases are queried once after the end of this phrase.
        A suffix phrase must follow directly. This means that the `at` parameter of a Token
        returned via ``start`` must be ``0`` and the Token must consume the content.

        **Tip**
            For content before the actual suffix that should not be part of the actual suffix
            (e.g., superfluous spaces), the `lstrip` of the Token parameter can be defined.

        **Note**
            If ``start`` returns a ``MaskToken``, sub-/suffix-phrases are **NOT** evaluated.
        """
        self.__suffix_phrases__.update(nodes)
        return self

    def add_suffix_recursion(self) -> Self:
        """Add the phrase to its own suffix-phrases for chained parsing.

        **Note**
            If ``start`` returns a ``MaskToken``, sub-/suffix-phrases are **NOT** evaluated.
        """
        self.__suffix_phrases__.add(self)
        return self

    def rm_sub_recursion(self) -> Self:
        """Remove the phrase from its own sub-phrases."""
        self.__sub_phrases__.discard(self)
        return self

    @overload
    def rm_suffixes(self, node: Phrase | Iterable[Phrase], *nodes: Phrase | Iterable[Phrase]) -> Self:
        ...

    @overload
    def rm_suffixes(self, node: Phrase | Iterable[Phrase], *nodes: Phrase | Iterable[Phrase]) -> Self:
        ...

    def rm_suffixes(self, *nodes: Phrase | Iterable[Phrase]) -> Self:
        """Remove one or more suffix phrases from the current phrase."""
        self.__suffix_phrases__ -= set(nodes)
        return self

    def rm_suffix_recursion(self) -> Self:
        """Remove the phrase from its own suffix-phrases."""
        self.__suffix_phrases__.discard(self)
        return self


class Root:
    """Represents the structure configuration root and parsing entry.
    All phrase configurations must be attached to this.
    """

    id: Any
    """[*ENTRY*] phrase id (default usage: only for debugging)"""

    TRootNode: Type[tokens.RootNode] = tokens.RootNode
    """[*ENTRY*] root-node class"""
    TDefaultToken: Type[tokens.OToken] = tokens.OToken
    """[*ENTRY*] default lv0-token class (default usage: if tokenize is not defined)"""
    TEOFToken: Type[tokens.EOF] = tokens.EOF
    """[*ENTRY*] EOF-token class"""
    TOpenEndToken: Type[tokens.OEOF] = tokens.OEOF
    """[*ENTRY*] initial end-token class"""
    TTokenizeStream: Type[streams.TokenizeStream] = streams.TokenizeStream
    """[*ENTRY*] tokenize stream class"""
    TDefaultTokenizeStream: Type[streams.DefaultTokenizeStream] = streams.DefaultTokenizeStream
    """[*ENTRY*] non-tokenize stream class (if tokenize is not defined)"""
    TParser: Type[streams.Parser] = streams.Parser
    """[*ENTRY*] stream class"""
    TTokenIndex: Type[indices.TokenIndex] = indices.ExtensiveTokenIndex
    """[*ENTRY*] index class"""

    __sub_phrases__: set[Phrase]

    @overload
    def __init__(
            self,
            *args,
            id: Any = ...,
            TRootNode: Type[tokens.RootNode] = tokens.RootNode,
            TDefaultToken: Type[tokens.OToken] = tokens.OToken,
            TEOFToken: Type[tokens.EOF] = tokens.EOF,
            TOpenEndToken: Type[tokens.OEOF] = tokens.OEOF,
            TTokenizeStream: Type[streams.TokenizeStream] = streams.TokenizeStream,
            TDefaultTokenizeStream: Type[streams.DefaultTokenizeStream] = streams.DefaultTokenizeStream,
            TParser: Type[streams.Parser] = streams.Parser,
            TTokenIndex: Type[indices.TokenIndex] = indices.ExtensiveTokenIndex,
            **kwargs
    ):
        ...

    @overload
    def __init__(self, *args, **kwargs):
        ...

    def __init__(self, *args, **kwargs):
        Phrase.__init__(self, *args, **kwargs)  # type: ignore
        if self.__class__.tokenize is Root.tokenize:
            # saves some operations in the parsing process
            # if tokenize has not been defined
            self.TTokenizeStream = self.TDefaultTokenizeStream

    starts: None
    """[*internal*] fake interface for duck-typing (cannot be overridden)"""
    @final
    def starts(*_, **__) -> None: raise RuntimeError(_[0].__class__.__name__ + f" ({Root.__name__}) added as a sub-phrase")

    ends: None
    """[*internal*] fake interface for duck-typing (cannot be overridden)"""
    @final
    def ends(*_, **__) -> None: return None

    def tokenize(self, stream: streams.TokenizeStream) -> Type[tokens.OToken] | Callable[[int, str], tokens.OToken]:
        ...

    @overload
    def add_subs(self, node: Phrase | Iterable[Phrase], *nodes: Phrase | Iterable[Phrase]) -> Self:
        ...

    @overload
    def add_subs(self, node: Phrase | Iterable[Phrase], *nodes: Phrase | Iterable[Phrase]) -> Self:
        ...

    def add_subs(self, *nodes: Phrase | Iterable[Phrase]) -> Self:
        """Add one or more sub phrases to the root phrase.

        When collections are passed as iterables of phrase objects, they are unpacked internally.
        """
        return Phrase.add_subs(self, *nodes)  # type: ignore

    @overload
    def rm_subs(self, node: Phrase | Iterable[Phrase], *nodes: Phrase | Iterable[Phrase]) -> Self:
        ...

    @overload
    def rm_subs(self, node: Phrase | Iterable[Phrase], *nodes: Phrase | Iterable[Phrase]) -> Self:
        ...

    def rm_subs(self, *nodes: Phrase | Iterable[Phrase]) -> Self:
        """Remove one or more phrases from the root phrase.

        When collections are passed as iterables of phrase objects, they are unpacked internally.
        """
        return Phrase.rm_subs(self, *nodes)  # type: ignore

    def parse_rows(self, rows: list[str]) -> tokens.RootNode:
        """Parses the given list of row strings and generates a Root object,
        which represents the hierarchical structure derived from the rows.

        **Note**
            Line breaks (``\\n \\r\\n``) are **NOT** interpreted automatically
            and must be present in the data if they are to be parsed.
        """
        entry = self.TRootNode(self)
        self.TParser(doc=rows, entry=entry).__run__()
        entry.end = self.TEOFToken(entry)
        return entry

    def parse_string(self, string: str) -> tokens.RootNode:
        """Parses a given string into a structured Root object.
        """
        return self.parse_rows(string.splitlines(keepends=True))

