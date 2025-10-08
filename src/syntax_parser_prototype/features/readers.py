from __future__ import annotations

from typing import TYPE_CHECKING, Generator, Any, Reversible, Callable, Literal

if TYPE_CHECKING:
    from typing_extensions import Self
    from ..main import tokens
    __TokenReversible__ = Reversible[tokens.Token]
else:
    __TokenReversible__ = Reversible

__all__ = (
    "TokenReader",
    "NodeTokenReader",
    "__TokenGenerators__",
    "__NodeTokenGenerators__",
    "__EndTokenGenerators__",
    "__OpenEndTokenGenerators__",
    "__EOFTokenGenerators__",
    "__RootNodeGenerators__",
)


class TokenReader(__TokenReversible__):
    """Provides functionality to iterate through tokens in a one-dimensional
    context and other structure-related methods.

    The default behavior as an iterator is to iterate one-dimensionally from the
    token that created the reader (anchor) to the last token (excl. the anchor).
    The iterator can be reversed using ``reversed(...)`` or ``__call__(reverse=True)``.

    Deviating contexts can be obtained via the properties:
        - ``thereafter``: from after the anchor to the end of data (excl. anchor) (default)
        - ``therebefore``: from the beginning of the data to before the anchor token (excl. anchor)
    """
    
    __token__: tokens.Token
    __fgen__: Callable[[], Generator[tokens.Token, Any, None]]
    __rgen__: Callable[[], Generator[tokens.Token, Any, None]]
    __context__: Literal["thereafter", "therebefore"]
    __reverse__: bool

    @property
    def content(self) -> str:
        """returns the content of the tokens in the reader's context as a string"""
        return "".join(i.content for i in self)
    
    def __init__(
            self,
            __token__: tokens.Token,
            __fgen__: Callable[[], Generator[tokens.Token, Any, None]],
            __rgen__: Callable[[], Generator[tokens.Token, Any, None]],
            __context__: Literal["thereafter", "therebefore"],
            __reverse__: bool,
    ):
        self.__token__ = __token__
        self.__fgen__ = __fgen__
        self.__rgen__ = __rgen__
        self.__context__ = __context__
        self.__reverse__ = __reverse__

    @classmethod
    def __default__(cls, token: tokens.Token) -> Self:
        return cls(
            token,
            token.__generators__.__thereafter__,
            token.__generators__.__r_thereafter__,
            "thereafter",
            False
        )

    def __next__(self) -> tokens.Token:
        return next(self.__gen__)

    __gen__: Generator[tokens.Token, Any, None]

    def __iter__(self) -> Self:
        self.__token__.__generators__.__instance__ = self.__token__
        if self.__reverse__:
            self.__gen__ = self.__rgen__()
        else:
            self.__gen__ = self.__fgen__()
        return self
    
    def __reversed__(self) -> Self:
        return self.__class__(
            self.__token__,
            self.__fgen__,
            self.__rgen__,
            self.__context__,
            not self.__reverse__
        )
    
    def __call__(self, reverse: bool = False) -> Self:
        return self.__class__(
            self.__token__,
            self.__fgen__,
            self.__rgen__,
            self.__context__,
            reverse
        )

    @property
    def thereafter(self) -> Self:
        """returns a new reader that iterates from after the anchor to the end of data (excl. anchor)"""
        return self.__default__(self.__token__)

    @property
    def therebefore(self) -> Self:
        """returns a new reader that iterates from the beginning of the data to before the anchor token (excl. anchor)"""
        return self.__class__(
            self.__token__,
            self.__token__.__generators__.__therebefore__,
            self.__token__.__generators__.__r_therebefore__,
            "therebefore",
            self.__reverse__
        )


class NodeTokenReader(TokenReader):
    """Provides functionality to iterate through tokens in a one-dimensional
    context and other structure-related methods.

    The default behavior as an iterator is to iterate one-dimensionally from the
    token that created the reader (anchor) to the last token (excl. the anchor).
    The iterator can be reversed using ``reversed(...)`` or ``__call__(reverse=True)``.

    Deviating contexts can be obtained via the properties:
        - ``thereafter``: from after the anchor to the end of data (excl. anchor) (default).
        - ``therebefore``: from the beginning of the data to before the anchor token (excl. anchor).
        - ``inner``: from the beginning of the inner tokens to the end of the inner tokens, recursively for sub-nodes (excl. node and end token at anchor's level).
        - ``branch``: from the beginning of the inner tokens to the end of the inner tokens, recursively for sub-nodes (incl. node and end token at anchor's level).
        - ``node_path``: structure path from the root node to the anchor node (incl.).
    """
    __token__: tokens.NodeToken
    __context__: Literal["thereafter", "therebefore", "inner", "branch", "node_path"]

    @property
    def node_path(self) -> Self:
        """returns a new reader that iterates through the structure path from the root node to the anchor node (incl.)"""
        return self.__class__(
            self.__token__,
            self.__token__.__generators__.__node_path__,
            self.__token__.__generators__.__r_node_path__,
            "node_path",  # type: ignore
            self.__reverse__
        )

    @property
    def inner(self) -> Self:
        """returns a new reader that iterates from the beginning of the inner tokens to the end of the inner tokens, recursively for sub-nodes (excl. node and end token at anchor's level)"""
        return self.__class__(
            self.__token__,
            self.__token__.__generators__.__inner__,
            self.__token__.__generators__.__r_inner__,
            "inner",  # type: ignore
            self.__reverse__
        )

    @property
    def branch(self) -> Self:
        """returns a new reader that iterates from the beginning of the inner tokens to the end of the inner tokens, recursively for sub-nodes (incl. node and end token at anchor's level)"""
        return self.__class__(
            self.__token__,
            self.__token__.__generators__.__branch__,
            self.__token__.__generators__.__r_branch__,
            "branch",  # type: ignore
            self.__reverse__
        )


class __TokenGenerators__:
    __instance__: tokens.Token

    def __get__(self, instance, owner) -> Self:
        self.__instance__ = instance
        return self

    def __thereafter__(self):
        __inst__ = self.__instance__
        try:
            i = __inst__.inner_index + 1
            for node in __inst__.node.__generators__.__r_node_path__():
                yield from node.__generators__.__inner_from_index__(i)
                yield node.end
                i = node.inner_index + 1
        except EOFError:
            return

    def __r_thereafter__(self):
        __inst__ = self.__instance__
        try:
            i = __inst__.inner_index + 1
            for node in __inst__.node.__generators__.__r_node_path__():
                yield node.end
                yield from node.__generators__.__r_inner_from_index__(i)
                i = node.inner_index + 1
        except EOFError:
            return

    def __r_therebefore__(self):
        __inst__ = self.__instance__
        try:
            i = __inst__.inner_index
            for node in __inst__.node.__generators__.__r_node_path__():
                yield from node.__generators__.__r_inner_until_index__(i)
                yield node
                i = node.inner_index
        except EOFError:
            return

    def __therebefore__(self):
        __inst__ = self.__instance__
        try:
            path = __inst__.node.__generators__.__node_path__()
            before = next(path)
            for node in path:
                yield before
                yield from before.__generators__.__inner_until_index__(node.inner_index)
                before = node
            yield before
            yield from before.__generators__.__inner_until_index__(__inst__.inner_index)
        except EOFError:
            return 


class ___EdgeTokenGenerators__(__TokenGenerators__):

    def __thereafter__(self):
        __inst__ = self.__instance__.next
        yield __inst__
        yield from __inst__.__generators__.__thereafter__()

    def __r_thereafter__(self):
        __inst__ = self.__instance__.next
        yield from __inst__.__generators__.__r_thereafter__()
        yield __inst__

    def __r_therebefore__(self):
        __inst__ = self.__instance__.previous
        yield __inst__
        yield from __inst__.__generators__.__r_therebefore__()

    def __therebefore__(self):
        __inst__ = self.__instance__.previous
        yield from __inst__.__generators__.__therebefore__()
        yield __inst__


class __NodeTokenGenerators__(___EdgeTokenGenerators__):
    __instance__: tokens.NodeToken

    def __r_node_path__(self):
        __inst__ = self.__instance__
        yield __inst__
        yield from __inst__.node.__generators__.__r_node_path__()

    def __node_path__(self):
        __inst__ = self.__instance__
        yield from __inst__.node.__generators__.__node_path__()
        yield __inst__

    def __inner__(self) -> Generator[tokens.NodeToken | tokens.EndToken | tokens.OpenEndToken | tokens.Token, Any, None]:
        """generate inner tokens recursively"""
        __inst__ = self.__instance__
        for t in __inst__.inner:
            if t.__fNODE__:
                yield t
                yield from t.__generators__.__inner__()
                yield t.end
            else:
                yield t

    def __r_inner__(self) -> Generator[tokens.NodeToken | tokens.EndToken | tokens.OpenEndToken | tokens.Token, Any, None]:
        """generate inner tokens recursively"""
        __inst__ = self.__instance__
        for t in reversed(__inst__.inner):
            if t.__fNODE__:
                yield t.end
                yield from t.__generators__.__r_inner__()
                yield t
            else:
                yield t

    def __branch__(self) -> Generator[tokens.NodeToken | tokens.EndToken | tokens.OpenEndToken | tokens.Token, Any, None]:
        """generate inner tokens recursively with this and this end"""
        __inst__ = self.__instance__
        yield __inst__
        yield from __inst__.__generators__.__inner__()
        yield __inst__.end

    def __r_branch__(self) -> Generator[tokens.NodeToken | tokens.EndToken | tokens.OpenEndToken | tokens.Token, Any, None]:
        """generate inner tokens recursively with this and this end"""
        __inst__ = self.__instance__
        yield __inst__.end
        yield from __inst__.__generators__.__r_inner__()
        yield __inst__

    def __inner_from_index__(self, i: int):
        __inst__ = self.__instance__
        for t in __inst__.inner[i:]:
            if t.__fNODE__:
                yield t
                yield from t.__generators__.__inner__()
                yield t.end
            else:
                yield t

    def __r_inner_from_index__(self, i: int):
        __inst__ = self.__instance__
        for t in reversed(__inst__.inner[i:]):
            if t.__fNODE__:
                yield t.end
                yield from t.__generators__.__r_inner__()
                yield t
            else:
                yield t

    def __r_inner_until_index__(self, i: int):
        __inst__ = self.__instance__
        for t in reversed(__inst__.inner[:i]):
            if t.__fNODE__:
                yield t.end
                yield from t.__generators__.__r_inner__()
                yield t
            else:
                yield t

    def __inner_until_index__(self, i: int):
        __inst__ = self.__instance__
        for t in __inst__.inner[:i]:
            if t.__fNODE__:
                yield t
                yield from t.__generators__.__inner__()
                yield t.end
            else:
                yield t


class __EndTokenGenerators__(___EdgeTokenGenerators__):
    __instance__: tokens.EndToken


class __OpenEndTokenGenerators__(__EndTokenGenerators__):
    __instance__: tokens.OpenEndToken

    def __r_thereafter__(self):
        __inst__ = self.__instance__
        t = __inst__.node.root.end
        if t is not __inst__:
            while t is not __inst__:
                yield t
                t = t.previous

    def __thereafter__(self):
        __inst__ = self.__instance__.next
        while True:
            yield __inst__
            __inst__ = __inst__.next


class __EOFTokenGenerators__(__OpenEndTokenGenerators__):
    __instance__: tokens.EOF

    def __r_thereafter__(self) -> None:
        raise EOFError

    def __thereafter__(self) -> None:
        raise EOFError


class __RootNodeGenerators__(__NodeTokenGenerators__):
    __instance__: tokens.RootNode

    def __r_node_path__(self):
        yield self.__instance__

    def __node_path__(self):
        yield self.__instance__

    def __therebefore__(self) -> None:
        raise EOFError

    def __r_therebefore__(self) -> None:
        raise EOFError
