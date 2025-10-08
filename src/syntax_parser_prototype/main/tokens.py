from __future__ import annotations

from xpropcache import PropCache

from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from typing_extensions import Self
    from . import streams, phrase
    from ..features import indices

from ..features import readers, tokenize

__all__ = (
    "Token",
    "NodeToken",
    "EndToken",
    "OpenEndToken",
    "MaskToken",
    "MaskNodeToken",
    "InstantToken",
    "InstantEndToken",
    "InstantNodeToken",
    "OToken",
    "EOF",
    "OEOF",
    "RootNode",
    "T_ANY_TOKEN",
    "T_RESULT_TOKEN",
    "T_INNER_TOKEN",
)


class Token:
    """Simple text content token and base type for all other tokens.

    Tokens of this type must be returned by ``Phrase.tokenize``
    or can represent a standalone token via ``Phrase.starts``.

    :param at: starting point of the token relative to ``stream.viewpoint``, in other words, in ``stream.unparsed``
        -- **including the part that is processed by a custom feature configuration**.
    :param to: ending point of the token relative to ``stream.viewpoint``, in other words, in ``stream.unparsed``
        -- **including the part that is processed by a custom feature configuration**.
    :param features: Features are special function parameters that can be passed to a node,
        end or standalone token that significantly influence the parsing process (see the module documentation of ``syntax_parser_prototype.features`` for more information).
    """

    id = "T"
    """[*ENTRY*] token id (default usage: only for debugging)"""

    __viewpoint__: int
    """[*internal*] viewpoint from which the stream was searched for"""
    __at__: int
    """[*internal*] starting point of the token relative to the viewpoint"""
    __to__: int
    """[*internal*] ending point of the token relative to the viewpoint"""

    content: str = ''
    """content of the token"""
    node: NodeToken
    """source node of the token"""
    row_no: int
    """row number where the token is located (starting from 0)"""
    phrase: phrase.Phrase | None = None  # set by stream in nodes or stand-alone-tokens
    """source phrase (only set in nodes or stand-alone-tokens)"""

    # @formatter:off
    # flags for token types
    __fINSTANT__    : bool = False
    __fNODE__       : bool = False
    __fEND__        : bool = False
    __fMASK__       : bool = False
    # @formatter:on

    __generators__: readers.__TokenGenerators__ = readers.__TokenGenerators__()

    @property
    def tokenReader(self) -> readers.TokenReader | readers.NodeTokenReader:
        """Provides functionality to iterate through tokens in a one-dimensional
        context and other structure-related methods.
        """
        return readers.TokenReader.__default__(self)

    __features__: tokenize.T_STD_FEATURES

    @property
    def __feat_phrase__(self) -> "phrase.Phrase | phrase.Root":
        return self.node.phrase

    @__feat_phrase__.setter
    def __feat_phrase__(self, phrase: "phrase.Phrase | phrase.Root") -> None:
        self.node.phrase = phrase

    def __init__(
            self,
            at: int,
            to: int,
            features: tokenize.T_STD_FEATURES = tokenize.BASE_T_FEAT,
    ):
        self.__at__ = at
        self.__to__ = to
        self.__features__ = features

    @property
    def __designated__(self) -> int:
        return self.__to__ - self.__at__

    def __lt__(self, other: Token) -> bool:
        """[*internal*] used to determine the priority of tokens

        The token that appeared first has the highest priority.
        If several tokens are in the same position and one of them has no content,
        this token is prioritized (null token); otherwise, the longest token (``__designated__``) has priority.
        """
        if self.__at__ != other.__at__:
            return self.__at__ < other.__at__
        else:
            designated = self.__designated__
            return not designated or designated > other.__designated__

    @property
    def column_start(self) -> int:
        """starting point of the token relative to the whole row"""
        return self.__viewpoint__ + self.__at__

    @property
    def column_end(self) -> int:
        """ending point of the token relative to the whole row"""
        return self.__viewpoint__ + self.__to__

    @property
    def data_start(self) -> int:
        """starting point of the token relative to the whole data"""
        return self.node.root.tokenIndex.data_start_of(self)

    @property
    def data_end(self) -> int:
        """ending point of the token relative to the whole data"""
        return self.data_start + self.len_token

    @property
    def len_token(self) -> int:
        """length of the token-content"""
        return len(self.content)

    @property
    def inner_index(self) -> int:
        """index of the token in its parent node"""
        return self.node.inner.index(self)

    @property
    def previous(self) -> T_RESULT_TOKEN:
        """previous token (in on the one-dimensional plane)"""
        if i := self.inner_index:
            t = self.node[i - 1]
            return t if not t.__fNODE__ else t.end
        else:
            return self.node

    @property
    def next(self) -> T_RESULT_TOKEN:
        """next token (in on the one-dimensional plane)"""
        if (i := self.inner_index + 1) < len(self.node.inner):
            return self.node[i]
        else:
            return self.node.end

    def replace_content(self, content: str, reindex: bool = True) -> None:
        """Replace the current content of the token with `content`. If the `reindex` is ``True`` (default),
        adjusts internal indexing of the following tokens and resets certain caches as necessary.

        The new content should be valid for the token; it is neither checked nor parsed.
        """
        if reindex and (diff := len(content) - self.len_token):
            for t in self.tokenReader.thereafter:
                if t.row_no != self.row_no:
                    break
                t.__viewpoint__ += diff
            self.node.root.tokenIndex.__char_cache_reset__(self.row_no)
        self.content = content

    def __str__(self) -> str:
        """return self.content"""
        return self.content

    def atConfirmed(self) -> None:
        """[*ENTRY*] (callback) called when the token has been confirmed (will be included in the result).

        Nodes and stand-alone tokens do not yet contain any `content` at this stage,
        and the attributes `__at__` and `__to__` can be modified by the featurization.
        """

    def atFeaturized(self) -> None:
        """[*ENTRY*] (callback) called after the token has been confirmed and featurized (only triggered for node and stand-alone tokens).
        """

    def __ini__(
            self,
            node: NodeToken,
            row_no: int,
            viewpoint: int,
    ) -> Self:
        """[*internal*] late bindings"""
        self.node = node
        self.row_no = row_no
        self.__viewpoint__ = viewpoint
        self.atConfirmed()
        return self

    def __ini_as_token__(self, stream: streams.Stream) -> Self:
        """[*internal*] late bindings for plain tokens"""
        return self.__ini__(stream.node, stream.row_no, stream.viewpoint)

    def __ini_from_tokenize__(self, content: str, stream: streams.TokenizeStream) -> Self:
        """[*internal*] late bindings for plain tokens"""
        self.content = content
        self.__to__ = self.__at__ + len(content)
        return self.__ini_as_token__(stream.__stream__)

    def __ini_as_node__(self, stream: streams.Stream) -> Self:
        """[*internal*] late bindings for node tokens"""
        return self.__ini__(stream.node, stream.row_no, stream.viewpoint)

    def __featurize__(self, p: streams.Parser) -> None:
        """[*internal*] processes token and configuration-related actions on the stream and result"""
        self.__features__(self, p)
        self.atFeaturized()


class NodeToken(Token):
    r"""Represents the beginning of a phrase as a token and
    contains subordinate tokens and the end token.

    ``Phrase.starts`` must return tokens of this type when a complex phrase starts.


    :param at: starting point of the token relative to ``stream.viewpoint``, in other words, in ``stream.unparsed``
        -- **including the part that is processed by a custom feature configuration**.
    :param to: ending point of the token relative to ``stream.viewpoint``, in other words, in ``stream.unparsed``
        -- **including the part that is processed by a custom feature configuration**.
    :param features: Features are special function parameters that can be passed to a node,
        end or standalone token that significantly influence the parsing process (see the module documentation of ``syntax_parser_prototype.features`` for more information).
    :param extras: Dynamic additional information about the node.
    """

    id = "N"
    """[*ENTRY*] token id (default usage: only for debugging)"""
    phrase: phrase.Phrase
    """source phrase"""
    inner: list[Token | NodeToken]
    """tokens of the phrase (excl. this node and the end token, can contain sub- or suffix-branches)"""
    end: EndToken | OpenEndToken
    """end token of the phrase"""

    class NodeExtras(dict):
        """dict-like with __getattr__ and __setattr__"""

        def __init__(self, extras: dict):
            super().__init__(extras)

        def __getattr__(self, attr):
            return self[attr]

        def __setattr__(self, attr, value):
            self[attr] = value

    extras: NodeExtras
    """dynamic state object about the branch"""

    __fNODE__: bool = True

    __generators__: readers.__NodeTokenGenerators__ = readers.__NodeTokenGenerators__()

    @property
    def tokenReader(self) -> readers.NodeTokenReader:
        """Provides functionality to iterate through tokens in a one-dimensional
        context and other structure-related methods.
        """
        return readers.NodeTokenReader.__default__(self)

    __features__: tokenize.T_NODE_FEATURES

    @property
    def __feat_phrase__(self) -> "phrase.Phrase | phrase.Root":
        return self.phrase

    @__feat_phrase__.setter
    def __feat_phrase__(self, phrase: "phrase.Phrase | phrase.Root") -> None:
        self.phrase = phrase

    def __init__(
            self,
            at: int,
            to: int,
            features: tokenize.T_NODE_FEATURES = tokenize.BASE_N_FEAT,
            **extras,
    ):
        Token.__init__(self, at, to, features)
        self.extras = extras  # type: ignore

    @PropCache.cached_property
    def root(self) -> RootNode:
        return self.node.root

    @property
    def len_inner(self) -> int:
        """length of all content within this branch (incl. subbranches, excl. this node and the end token)"""
        return sum(t.len_token for t in self.tokenReader.inner)

    @property
    def len_branch(self) -> int:
        """length of all content in this branch (incl. subbranches, this node and the end token)"""
        return self.len_token + self.len_inner + self.end.len_token

    @property
    def previous(self) -> T_RESULT_TOKEN:
        if i := self.inner_index:
            t = self.node[i - 1]
            return t if not t.__fNODE__ else t.end
        else:
            return self.node

    @property
    def next(self) -> T_RESULT_TOKEN:
        if self.inner:
            return self[0]
        else:
            return self.end

    def __getitem__(self, item: int) -> T_INNER_TOKEN:
        """get inner token on index"""
        return self.inner[item]

    def __ini__(self, node: NodeToken, row_no: int, viewpoint: int) -> Self:
        self.inner = list()
        self.end = self.phrase.TOpenEndToken(self)
        self.extras = self.NodeExtras(self.extras)
        return super().__ini__(node, row_no, viewpoint)

    def __ini_as_token__(self, stream: streams.Stream) -> Self:
        raise TypeError(f"{self.__class__} (NodeToken) cannot be used as a plain Token")

    def __ends__(self, stream: streams.Stream) -> EndToken | None:
        """[*internal*] shortcut"""
        return self.phrase.ends(stream)


class EndToken(Token):
    """Represents the end of a phrase.

    ``Phrase.ends`` must return tokens of this type when a complex phrase ends.

    :param at: starting point of the token relative to ``stream.viewpoint``, in other words, in ``stream.unparsed``
        -- **including the part that is processed by a custom feature configuration**.
    :param to: ending point of the token relative to ``stream.viewpoint``, in other words, in ``stream.unparsed``
        -- **including the part that is processed by a custom feature configuration**.
    :param features: Features are special function parameters that can be passed to a node,
        end or standalone token that significantly influence the parsing process (see the module documentation of ``syntax_parser_prototype.features`` for more information).
    """

    id = "E"
    """[*ENTRY*] token id (default usage: only for debugging)"""
    phrase: None
    """is None for EndToken"""

    __fEND__: bool = True

    __generators__: readers.__EndTokenGenerators__ = readers.__EndTokenGenerators__()

    def __init__(self, at: int, to: int, features: tokenize.T_STD_FEATURES = tokenize.BASE_E_FEAT):
        super().__init__(at, to, features)

    @property
    def inner_index(self) -> None:
        raise ValueError(f"{self.__class__} (EndToken) is never in inner")

    @property
    def previous(self) -> T_RESULT_TOKEN:
        if self.node.inner:
            t = self.node[-1]
            return t if not t.__fNODE__ else t.end
        else:
            return self.node

    @property
    def next(self) -> T_RESULT_TOKEN:
        if (i := self.node.inner_index + 1) < len(self.node.node.inner):
            return self.node.node[i]
        else:
            return self.node.node.end

    def __ini__(self, node: NodeToken, row_no: int, viewpoint: int) -> Self:
        return super().__ini__(node, row_no, viewpoint)


class OpenEndToken(Token):
    """[*internal*] Represents the non-end of a phrase.

    This type is set by default to ``NodeToken.end`` until an ``EndToken`` replaces it
    or remains in the result if none was found until the end.
    Acts as an interface to the last seen token of the phrase for duck typing.
    """

    id = "O"
    __fEND__: bool = True
    __generators__: readers.__OpenEndTokenGenerators__ = readers.__OpenEndTokenGenerators__()

    @property
    def __viewpoint__(self) -> int:
        return self.last_token.__viewpoint__

    @property
    def __at__(self) -> int:
        return self.last_token.__to__

    @property
    def row_no(self) -> int:
        return self.last_token.row_no

    def __init__(self, node: NodeToken):  # noqa: super-init-not-called
        self.content = ""
        self.node = node

    @property
    def last_token(self) -> T_INNER_TOKEN:
        if self.node.inner:
            return self.node[-1]
        else:
            return self.node

    @property
    def inner_index(self) -> None:
        """raises ValueError"""
        return EndToken.inner_index.fget(self)

    @property
    def previous(self) -> T_RESULT_TOKEN:
        if self.node.inner:
            t = self.node[-1]
            return t if not t.__fNODE__ else t.end
        else:
            return self.node

    @property
    def next(self) -> OpenEndToken | OEOF | EOF:
        """next token (in on the one-dimensional plane). can be another OpenEndToken, OEOF or EOF from here"""
        return self.node.node.end

    def replace_content(self, content: str, reindex: bool = True) -> None:
        """raises ValueError"""
        raise ValueError(f"{self.__class__} (OpenEndToken) should not contain any content")


class MaskToken(Token):
    """Special standalone token type that can be returned by ``Phrase.starts``.

    Instead of the start of this phrase, the content is then assigned to the parent node.
    This token type will never be present in the result.

    **Note**
            If ``start`` returns a ``MaskToken``, sub-/suffix-phrases of this Phrase are **NOT** evaluated.

    :param at: starting point of the token relative to ``stream.viewpoint``, in other words, in ``stream.unparsed``
        -- **including the part that is processed by a custom feature configuration**.
    :param to: ending point of the token relative to ``stream.viewpoint``, in other words, in ``stream.unparsed``
        -- **including the part that is processed by a custom feature configuration**.
    """

    id = "?"  # never present in the result
    __fMASK__: bool = True

    def __init__(self, at: int, to: int):
        super().__init__(at, to)


class MaskNodeToken(MaskToken, NodeToken):
    """Special node token type that can be returned by ``Phrase.starts``.

    Starts a masking phrase whose content is assigned to the parent node.
    This token type will never be present in the result.

    **Note**
            If ``start`` returns a ``MaskToken``, sub-/suffix-phrases of this Phrase are **NOT** evaluated.

    :param at: starting point of the token relative to ``stream.viewpoint``, in other words, in ``stream.unparsed``
        -- **including the part that is processed by a custom feature configuration**.
    :param to: ending point of the token relative to ``stream.viewpoint``, in other words, in ``stream.unparsed``
        -- **including the part that is processed by a custom feature configuration**.
    """

    id = "?N"  # never present in the result

    def __init__(self, at: int, to: int):
        MaskToken.__init__(self, at, to)


class InstantToken(Token):
    """Special standalone token type that can be returned by ``Phrase.starts``.

    Prevents comparison of priority with other tokens and accepts the token directly.

    :param at: starting point of the token relative to ``stream.viewpoint``, in other words, in ``stream.unparsed``
        -- **including the part that is processed by a custom feature configuration**.
    :param to: ending point of the token relative to ``stream.viewpoint``, in other words, in ``stream.unparsed``
        -- **including the part that is processed by a custom feature configuration**.
    :param features: Features are special function parameters that can be passed to a node,
        end or standalone token that significantly influence the parsing process (see the module documentation of ``syntax_parser_prototype.features`` for more information).
    """

    id = "i"
    """[*ENTRY*] token id (default usage: only for debugging)"""
    __fINSTANT__: bool = True

    def __init__(self, at: int, to: int, features: tokenize.T_STD_FEATURES = tokenize.BASE_T_FEAT):
        super().__init__(at, to, features)

    def __lt__(self, other: Token) -> bool:
        return True


class InstantEndToken(EndToken, InstantToken):
    """Special end token type that can be returned by ``Phrase.ends``.

    Prevents comparison of priority with other tokens and accepts the token directly.

    :param at: starting point of the token relative to ``stream.viewpoint``, in other words, in ``stream.unparsed``
        -- **including the part that is processed by a custom feature configuration**.
    :param to: ending point of the token relative to ``stream.viewpoint``, in other words, in ``stream.unparsed``
        -- **including the part that is processed by a custom feature configuration**.
    :param features: Features are special function parameters that can be passed to a node,
        end or standalone token that significantly influence the parsing process (see the module documentation of ``syntax_parser_prototype.features`` for more information).
    """

    id = "iE"
    """[*ENTRY*] token id (default usage: only for debugging)"""

    def __init__(self, at: int = 0, to: int = 0, features: tokenize.T_STD_FEATURES = tokenize.BASE_E_FEAT):
        super().__init__(at, to, features)


class InstantNodeToken(NodeToken, InstantToken):
    """Special node token type that can be returned by ``Phrase.starts``.

    Prevents comparison of priority with other tokens and accepts the token directly.

    :param at: starting point of the token relative to ``stream.viewpoint``, in other words, in ``stream.unparsed``
        -- **including the part that is processed by a custom feature configuration**.
    :param to: ending point of the token relative to ``stream.viewpoint``, in other words, in ``stream.unparsed``
        -- **including the part that is processed by a custom feature configuration**.
    :param features: Features are special function parameters that can be passed to a node,
        end or standalone token that significantly influence the parsing process (see the module documentation of ``syntax_parser_prototype.features`` for more information).
    """

    id = "iN"
    """[*ENTRY*] token id (default usage: only for debugging)"""

    def __init__(self, at: int, to: int, features: tokenize.T_NODE_FEATURES = tokenize.BASE_N_FEAT, **extras):
        super().__init__(at, to, features, **extras)


class OToken(Token):
    """Represents an inner token for the root phrase when no user-defined phrase is active.
    """

    id = "o"
    """[*ENTRY*] token id (default usage: only for debugging)"""

    phrase: phrase.Root | None


class EOF(EndToken):
    """Represents the end of the parsed input, set to ``RootNode.end``
    (has no content but is a valid token to be included in the result).
    """

    id = "EOF"
    """[*ENTRY*] token id (default usage: only for debugging)"""

    __generators__: readers.__EOFTokenGenerators__ = readers.__EOFTokenGenerators__()

    def __init__(self, root: RootNode):
        last = root[-1] if root.inner else root
        EndToken.__init__(self, last.__to__, last.__to__)
        self.__ini__(root, last.row_no, last.__viewpoint__)

    @property
    def next(self) -> None:
        """raises EOFError"""
        raise EOFError


class OEOF(OpenEndToken):
    """[*internal*] Represents the non-end of the parsed input, set to ``RootNode.end``.

    This type is set by default until the ``EOF`` replaces it at the end of the process
    (will never be included in the result).
    """

    id = "OOEF"
    """[*ENTRY*] token id (default usage: only for debugging)"""

    @property
    def next(self) -> None:
        """raises EOFError"""
        raise EOFError


class RootNode(NodeToken):
    """Represents the root of the parsed input and contains all other tokens
    (has no content but is a valid token to represent the result root).
    """

    id = "R"
    """[*ENTRY*] token id (default usage: only for debugging)"""
    phrase: phrase.Root
    """Main"""

    inner: list[OToken | NodeToken]
    """tokens of the phrase (excl. this node and the end token, can contain sub- or suffix-branches)"""
    end: EOF | OEOF
    """end token representing the end of the parsed input"""

    tokenIndex: indices.TokenIndex | indices.NoneTokenIndex | indices.ExtensiveTokenIndex

    __generators__: readers.__RootNodeGenerators__ = readers.__RootNodeGenerators__()

    def __init__(self, phrase: "phrase.Root"):
        self.phrase = phrase
        self.tokenIndex = phrase.TTokenIndex()
        super().__init__(0, 0)
        self.__ini__(self, 0, 0)

    def __lt__(self, other: NodeToken):
        return True  # never called in parsing

    @property
    def root(self) -> Self:
        """returns self"""
        return self

    @property
    def inner_index(self) -> None:
        """raises EOFError"""
        raise EOFError

    @property
    def previous(self) -> None:
        """raises EOFError"""
        raise EOFError

    def __ends__(self, stream: streams.Stream) -> None:
        """return None"""
        return None

    def __bool__(self):
        """whether any content is present in the result"""
        return self.content or self.inner or self.end.content


T_RESULT_TOKEN = Union[
    Token,
    NodeToken,
    EndToken,
    OpenEndToken,
    InstantToken,
    InstantEndToken,
    InstantNodeToken,
    OToken,
    EOF,
    RootNode,
]
T_INNER_TOKEN = Union[
    Token,
    NodeToken,
    InstantToken,
    InstantNodeToken,
    OToken,
]
T_ANY_TOKEN = Union[
    Token,
    NodeToken,
    EndToken,
    OpenEndToken,
    MaskToken,
    MaskNodeToken,
    InstantToken,
    InstantEndToken,
    InstantNodeToken,
    OToken,
    EOF,
    OEOF,
    RootNode,
]
T_BASE_TOKENS = Union[
    Token,
    NodeToken,
    EndToken,
]
T_START_TOKENS = Union[
    Token,
    NodeToken,
]
