from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .tokens import *
    from .streams import *

__all__ = (
    "NodeTokenizeFuture",
    "NodeTokenExtras",
)


class NodeTokenizeFuture:
    node: NodeToken
    ran: int
    column_start: int

    def __init__(self, node: NodeToken, content: str):
        self.node = node
        self.ran = len(content)

    def __run__(self, stream: Stream):
        if self.ran:
            self.column_start = self.node.column_end + self.ran
            self.node.phrase.TTokenizeStream(stream, self).__run__()
        del self.node.__tokenize__


class NodeTokenExtras:

    def __init__(self, extras: dict):
        self.__dict__.update(extras)

    def __getattr__(self, attr):
        return suber().__getattr__(attr)
