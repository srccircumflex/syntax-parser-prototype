from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import tokens, streams

__all__ = (
    "AdvanceError",
    "TokenizationAdvanceError",
    "NullTokenError",
    "FeatureError",
)


class AdvanceError(RuntimeError):
    """raised when a stream is stuck without advancing"""

    def __init__(
            self,
            msg: str,
            node: tokens.NodeToken,
            row_no: int,
            row: str,
            cursor: int,
            unparsed: str,
    ):
        super().__init__(
            msg
            + f"\n"
              f"in node           : {node!r}\n"
              f"row     [no. {row_no:4}]: {row!r}\n"
              f"unparsed[cur {cursor:4}]: {unparsed!r}"
        )


class TokenizationAdvanceError(AdvanceError):
    """raised when tokenization stuck without advancing"""

    def __init__(self, stream: streams.TokenizeStream):
        AdvanceError.__init__(
            self,
            f"{stream.__class__.__name__} was not advanced by the tokenization of: {stream.__stream__.node.phrase!r}",
            stream.__stream__.node,
            stream.__stream__.row_no,
            stream.__stream__.row,
            stream.__stream__.viewpoint + stream.__cursor__,
            stream.unparsed,
        )


class NullTokenError(AdvanceError):
    """raised when the stream encounters an illegal null token"""

    def __init__(self, stream: streams.Stream, nulltoken: tokens.Token):
        AdvanceError.__init__(
            self,
            f"{stream.__class__.__name__} encountered an illegal null token: {nulltoken!r}",
            stream.node,
            stream.row_no,
            stream.row,
            stream.__position__,
            stream.unparsed,
        )


class FeatureError(AdvanceError):
    """raised when a feature is faulted"""

    def __init__(self, token: tokens.Token, parser: streams.Parser):
        AdvanceError.__init__(
            self,
            f"Faulted featuring of Token: {token!r} ({token.__to__=} < {token.__at__=})\n",
            parser.node,
            parser.row_no,
            parser.row,
            parser.__position__,
            parser.unparsed,
        )
