"""
Features are special function parameters that can be passed to a node,
end or standalone token that significantly influence the parsing process.

Stripping features:
    - ``LStrip``
        stripping an amount of content before the token to the currently
        active branch before the processes of the token
    - ``RTokenize``
        stripping an amount of content after the token to the currently
        active branch after the processes of this token

Context-influencing features:
    - ``SwitchTo``, ``SwitchPh``
        modify the phrase association in a specific context
    - ``ForwardTo``
        querying a phrase start directly after the token

Features can be linked to form a selective process, but a basic logic is followed internally during execution:
    ``LStrip`` is always executed before the actual token is processed, RTokenize's afterward.
    There can be several ``SwitchTo`` at any point between these features.
    Finally, a single ``ForwardTo`` is executed if available.

::

    Token(
        ...,
        features=SwitchTo(<phrase>) | LStrip(3) | SwitchTo(<phrase>) | LStrip(1) | RTokenize(1) | SwitchTo(<phrase>) | ForwardTo(phrase)
    )

"""
from __future__ import annotations

from email.charset import BASE64
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from typing_extensions import Self
    from ..main import phrase, tokens, streams

from ..exceptions import *


__all__ = (
    "Feat",
    "LStrip",
    "RTokenize",
    "SwitchTo",
    "SwitchPh",
    "ForwardTo",
    "BaseFeat",
    "BASE_T_FEAT",
    "BASE_N_FEAT",
    "BASE_E_FEAT",
    "T_STD_FEATURES",
    "T_NODE_FEATURES",
)


class Feat:

    __left__: list[LStrip | SwitchTo]
    __right__: list[RTokenize | SwitchTo]
    __rval__: int = 0
    __forward__: ForwardTo = None

    __swtarg__: list[LStrip | SwitchTo] | list[RTokenize | SwitchTo]

    def __init__(self):
        self.__left__ = self.__swtarg__ = list()
        self.__right__ = list()
        self.__or__(self)

    def __or__(
            self,
            other: Union[LStrip | RTokenize | SwitchTo | ForwardTo]
    ) -> Self:
        if isinstance(other, ForwardTo):
            self.__forward__ = other
        elif isinstance(other, LStrip):
            self.__left__.append(other)
        elif isinstance(other, RTokenize):
            self.__right__.append(other)
            self.__rval__ += other.__value__
            self.__swtarg__ = self.__right__
        else:
            self.__swtarg__.append(other)
        return self

    def __call__(self, token: tokens.T_BASE_TOKENS, parser: streams.Parser):
        parser.__carry__(token.__at__)  # carry for parsed remain

        for left in self.__left__:
            left.__run__(token, parser)  # carries __at__

        token.__to__ -= self.__rval__

        if token.__at__ > token.__to__:
            raise FeatureError(token, parser)

        BaseFeat(token).__fun__(token, parser, token.__designated__)

        for right in self.__right__:
            right.__run__(token, parser)  # carries parser

        if self.__forward__:
            self.__forward__.__run__(token, parser)


class LStrip(Feat):
    """Feature for stripping an amount of content before the token to the currently
    active branch before the processes of the token.

    (enables the early activation of a token and extends the designated length, thereby increasing priority)

    Example::

        stream.unparsed  # "foo*bar"

        Token(
            at=0, to=4,  # "foo*",
            LStrip(3)    # "foo" is parsed as a part of the current phrase
        )
        # the content of this token will be "*"
    """

    def __init__(self, value: int):
        self.__value__ = value
        super().__init__()

    def __run__(self, token: tokens.Token, parser: streams.Parser):
        token.__at__ += self.__value__
        token.__feat_phrase__.TTokenizeStream(parser, token, token, "<").__run__()
        parser.__carry__(self.__value__)


class RTokenize(Feat):
    """Feature for stripping an amount of content after the token to the currently
    active branch after the processes of this token.

    (extends the designated length of a token, thereby increasing its priority)

    ::

        stream.unparsed   # "foo*bar"

        Token(
            at=3, to=7,   # "*bar",
            RTokenize(3)  # “bar” is parsed as part of the active/activated phrase in a separate token
        )
        # the content of this token will be "*"
    """

    def __init__(self, value: int):
        self.__value__ = value
        super().__init__()

    column_start: int

    def __run__(self, token: tokens.T_BASE_TOKENS, parser: streams.Parser):
        self.column_start = parser.viewpoint + self.__value__
        token.__feat_phrase__.TTokenizeStream(
            parser,
            self,
            token,
            ">").__run__()
        parser.__carry__(self.__value__)


class SwitchTo(Feat):
    """Feature for modify the phrase association in a specific context.

    Changes the phrase in the context of the associated token.
    This means that for node tokens, the phrase of this node is changed,
    not the phrase that contains the node (``SwitchPh`` can be used for
    deviating behavior with node tokens).
    For stand-alone and end tokens, their parent phrase is changed.

    This feature also influences the context in which ``LStrip`` and ``RTokenize`` are processed.

    The previous phrase is lost in the process, in future the configuration
    of this phrase will be applied in the branch (``Phrase.ends``, ``Phrase.tokenize``, ...)
    """

    def __init__(self, value: phrase.Phrase | phrase.Root):
        self.__value__ = value
        super().__init__()

    def __run__(self, token: tokens.T_BASE_TOKENS, parser: streams.Parser):
        token.__feat_phrase__ = self.__value__


class SwitchPh(Feat):
    """Feature for modify the phrase association in a specific context.

    In contrast to ``SwitchTo``, the phrase that contains the associated token
    is explicitly changed. The feature only makes sense for node tokens, as only
    here does the behavior differ in comparison to ``SwitchTo``.

    This feature does not affect the context in which ``LStrip`` and ``RTokenize`` are processed for node tokens.

    The previous phrase is lost in the process, in future the configuration
    of this phrase will be applied in the branch (``Phrase.ends``, ``Phrase.tokenize``, ...)
    """

    def __init__(self, value: phrase.Phrase | phrase.Root):
        self.__value__ = value
        super().__init__()

    def __run__(self, token: tokens.T_BASE_TOKENS, parser: streams.Parser):
        parser.node.phrase = self.__value__


class ForwardTo(Feat):
    """Feature for querying a phrase start directly after the token.

    Will execute ``<Phrase>.start(...)`` of the passed phrase object and change directly if positive
    (the previous phrase remains as a parent).
    """

    def __init__(self, value: phrase.Phrase):
        self.__value__ = value
        super().__init__()

    def __run__(self, token: tokens.Token, parser: streams.Parser):
        if item := self.__value__.starts(parser):
            item.phrase = self.__value__
            parser.__sub_item__(item)


class _BaseFeat:

    def __fun__(self, token: tokens.Token, parser: streams.Parser, __carry__: int):
        token.content = parser.row[
            token.__viewpoint__ + token.__at__:token.__viewpoint__ + token.__to__
        ]
        parser.__carry__(__carry__)

    def __call__(self, token: tokens.Token, parser: streams.Parser):
        self.__fun__(token, parser, token.__to__)


class _TokenBaseFeat(_BaseFeat):

    def __fun__(self, token: tokens.Token, parser: streams.Parser, __carry__: int):
        super().__fun__(token, parser, __carry__)
        parser.node.inner.append(token)


class _NodeBaseFeat(_TokenBaseFeat):

    def __fun__(self, token: tokens.NodeToken, parser: streams.Parser, __carry__: int):
        super().__fun__(token, parser, __carry__)
        parser.node = token


class _EndBaseFeat(_BaseFeat):

    def __fun__(self, token: tokens.EndToken, parser: streams.Parser, __carry__: int):
        super().__fun__(token, parser, __carry__)
        parser.node.end = token
        parser.__suffix_phrases__ = token.node.phrase.__suffix_phrases__
        # return to the parent node
        parser.node = token.node.node


BASE_T_FEAT = _TokenBaseFeat()
BASE_N_FEAT = _NodeBaseFeat()
BASE_E_FEAT = _EndBaseFeat()


def BaseFeat(token: tokens.T_BASE_TOKENS):
    if token.__fEND__:
        return BASE_E_FEAT
    elif token.__fNODE__:
        return BASE_N_FEAT
    else:
        return BASE_T_FEAT


T_STD_FEATURES = Union[LStrip, RTokenize, SwitchTo, ForwardTo]
T_NODE_FEATURES = Union[T_STD_FEATURES, SwitchPh]
