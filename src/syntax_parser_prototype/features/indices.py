"""
These classes are used to organize and manage token data,
including indexing and caching operations for efficient processing.

Configuration parameters as types for RootPhrase.

Classes:
    - TokenIndex: Template class.
    - NoneTokenIndex: A lightweight implementation for scenarios without indexing.
    - ExtensiveTokenIndex: A comprehensive implementation with detailed caching
      and record management.


"""

from __future__ import annotations

from typing import TYPE_CHECKING

from xpropcache import PropCache

if TYPE_CHECKING:
    from ..main import streams, tokens


__all__ = (
    "TokenIndex",
    "NoneTokenIndex",
    "ExtensiveTokenIndex",
)


class _CacheKeys:
    CHARCOUNT = 0b0001


class TokenIndex:
    """Template class

    **(see module docstring)**"""

    def __at_row__(self, p: streams.Parser):
        # register last node before current row
        ...

    def __at_stale__(self, p: streams.Parser):
        # find and register last token before current row
        ...

    def __build__(self):
        # finalize index
        ...

    def __char_cache_reset__(self, from_i: int = 0):
        ...

    def data_start_of(self, token: tokens.T_BASE_TOKENS) -> int:
        """starting point of the token relative to the whole data"""
        return sum(t.len_token for t in token.tokenReader.therebefore)


class NoneTokenIndex(TokenIndex):
    """Can be used to save operations when no index is needed.

    (configured as a type in the root phrase)
    """
    ...


class ExtensiveTokenIndex(TokenIndex):
    """A comprehensive implementation with detailed caching and record management.

    Creates a record object (ExtensiveTokenIndex.Record) 
    for each row from the parsing input that can be accessed
    via index<ExtensiveTokenIndex>[row_no].

    ExtensiveTokenIndex.Record provides some localization utilities.

    (configured as a type in the root phrase)
    """

    @PropCache
    class Record:
        __idx__: ExtensiveTokenIndex

        def __init__(
                self,
                first_token: tokens.T_BASE_TOKENS,
                __idx__: ExtensiveTokenIndex,
        ):
            self.__idx__ = __idx__
            self.first_token = first_token

        first_token: tokens.T_BASE_TOKENS
        """first token in the row"""

        @PropCache.cached_property
        def row_tokens(self) -> list[tokens.T_BASE_TOKENS]:
            """all tokens in the row"""
            tokens = [self.first_token]
            for token in self.first_token.tokenReader.thereafter:
                if token.row_no != self.row_no:
                    break
                tokens.append(token)
            return tokens

        @PropCache.cached_property
        def last_token(self) -> tokens.T_BASE_TOKENS:
            """last token in the row"""
            return self.row_tokens[-1]

        @PropCache.cached_property
        def row_no(self) -> int:
            """row number (starting from 0)"""
            return self.first_token.row_no

        @PropCache.cached_property(_CacheKeys.CHARCOUNT)
        def data_start(self) -> int:
            """starting point of the row relative to the whole data"""
            if self.row_no:
                return self.__idx__[self.row_no - 1].data_end
            else:
                return self.first_token.column_start

        @PropCache.cached_property(_CacheKeys.CHARCOUNT)
        def data_end(self) -> int:
            """ending point of the row relative to the whole data"""
            return self.data_start + self.len_row

        @PropCache.cached_property(_CacheKeys.CHARCOUNT)
        def len_row(self) -> int:
            """length of the row content"""
            return self.last_token.column_end

        def token_at(self, col_no: int) -> tokens.T_RESULT_TOKEN | None:
            """returns the token at the given column"""
            for token in self.row_tokens:
                if token.column_end > col_no:
                    return token
            else:
                return None

    __temp__: list[tokens.T_BASE_TOKENS]
    __stack__: list[Record]

    def __init__(self):
        self.__temp__ = list()

    def __at_row__(self, p: streams.Parser):
        # register last node before current row
        self.__temp__.append(p.node)

    def __at_stale__(self, p: streams.Parser):
        # register last node before current row
        token = p.node
        if p.node.__viewpoint__:
            # parser is stalled -> find last token before current row
            try:
                for _token in p.node.tokenReader.therebefore(reverse=True):
                    if _token.row_no != p.row_no:
                        break
                    token = _token
            except EOFError:
                pass
        self.__temp__.append(token)

    def __build__(self):
        # finalize index
        self.__stack__ = list()
        for row_no, token in enumerate(self.__temp__):
            if token.row_no != row_no:
                # find first token in row
                for token in token.tokenReader.thereafter:
                    if token.row_no == row_no:
                        break
            self.__stack__.append(self.Record(token, self))
        del self.__temp__

    def __getitem__(self, row_no: int) -> Record:
        return self.__stack__[row_no]

    def __char_cache_reset__(self, from_i: int = 0):
        for record in self.__stack__[from_i:]:
            PropCache.cp_reset_by_flag(record, _CacheKeys.CHARCOUNT)

    def data_start_of(self, token: tokens.T_BASE_TOKENS) -> int:
        """starting point of the token relative to the whole data"""
        return self.__stack__[token.row_no].data_start + token.column_start

    def get_token_at_coord(self, row_no: int, col_no: int) -> tokens.T_RESULT_TOKEN | None:
        """returns the token at the given coordinate"""
        return self.__stack__[row_no].token_at(col_no)

    def get_token_at_cursor(self, cursor: int) -> tokens.T_RESULT_TOKEN | None:
        """returns the token at the given data cursor (relative to the whole data)"""
        for record in self.__stack__:
            if record.data_end > cursor:
                return record.token_at(cursor - record.data_start)
        else:
            return None
