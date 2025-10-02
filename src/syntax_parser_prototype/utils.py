from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .tokens import *
    from .streams import *
    from .phrases import *

__all__ = (
    "NodeTokenizeFuture",
    "EndTokenizeFuture",
    "NodeTokenExtras",
)


class _TokenizeFuture:
    node: NodeToken
    ran: int

    def __init__(self, node: NodeToken, content: str):
        self.node = node
        self.ran = len(content)

    def __run__(self, stream: Stream):
        ...

    def __len__(self):
        return self.ran


class NodeTokenizeFuture(_TokenizeFuture):

    def __run__(self, stream: Stream):
        if self.ran:
            self.column_start = self.node.column_end + self.ran  # (fake delimiter)
            self.node.phrase.TTokenizeStream(stream, self, "n").__run__()
            stream.__carry__(self.ran)


class EndTokenizeFuture(_TokenizeFuture):

    def __run__(self, stream: Stream):
        if self.ran:
            stream.__carry__(self.node.end.seen_start)  # carry for parsed remain
            self.node.end.viewpoint = stream.viewpoint + self.ran
            self.node.end.seen_start = 0
            self.node.phrase.TTokenizeStream(stream, self.node.end, "e").__run__()
            stream.__carry__(self.ran)


class NodeTokenExtras(dict):

    def __init__(self, extras: dict):
        super().__init__(extras)

    def __getattr__(self, attr):
        return self[attr]
