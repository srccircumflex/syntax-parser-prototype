from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar, Any

__all__ = (
    "TV_NODE_TOKEN",
    "TV_ROOT_NODE",
    "TV_PHRASE",
    "TV_ROOT",
)

if TYPE_CHECKING:
    from . import *

    TV_NODE_TOKEN = TypeVar("TV_NODE_TOKEN", bound=NodeToken | RootNode, covariant=True)
    TV_ROOT_NODE = TypeVar("TV_ROOT_NODE", bound=RootNode, covariant=True)
    TV_PHRASE = TypeVar("TV_PHRASE", bound=Phrase | Root, covariant=True)
    TV_ROOT = TypeVar("TV_ROOT", bound=Root, covariant=True)
else:
    TV_NODE_TOKEN = TypeVar("TV_NODE_TOKEN", bound=Any)
    TV_ROOT_NODE = TypeVar("TV_ROOT_NODE", bound=Any)
    TV_PHRASE = TypeVar("TV_PHRASE", bound=Any)
    TV_ROOT = TypeVar("TV_ROOT", bound=Any)
