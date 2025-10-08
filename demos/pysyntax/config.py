from __future__ import annotations

import builtins
import keyword
import re
from typing import Type, Callable

from src.syntax_parser_prototype import *
from src.syntax_parser_prototype import debug
from src.syntax_parser_prototype.features.tokenize import *

#####################################################################################################
# PHRASES CONFIGURATION


DEBUG_ANCHORS: dict[str, Token] = dict()


class CommentPhrase(Phrase):
    id = "comment"

    class CommentNode(NodeToken):
        id = "comment"

    class CommentContent(Token):
        id = "comment-content"

    class DebugAnchor(Token):
        id = "comment-debug-anchor"

        def atConfirmed(self):
            DEBUG_ANCHORS[self.content[1:]] = self

    debug.html_server.token_css[Token] = "color: white;"

    def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
        if m := re.search("#(.*$)", stream.unparsed):
            return self.CommentNode(m.start(), m.end(), RTokenize(len(m.group(1))))

    def tokenize(self, stream: TokenizeStream) -> Type[Token] | Callable[[int, str], Token]:
        if stream.eat_n(1) == "$":  # $anchor1
            stream.eat_until(re.compile("\\W"))
            return self.DebugAnchor
        else:
            stream.eat_until(re.compile("\\$"))
            return self.CommentContent


comment_phrase = CommentPhrase()


class BackslashEscPhrase(Phrase):
    id = "backslash-esc"

    class Token(Token):
        id = "backslash-esc"

    debug.html_server.token_css[Token] = "color: orange;"

    def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
        if m := re.search("\\\\(N\\{\\w+}|\\d{3}|x[a-fA-F0-9]{2}|u\\d{4}|U\\d{8}|(.))", stream.unparsed, re.DOTALL):
            return self.Token(m.start(), m.end())


_backslash_phrase = BackslashEscPhrase()


class StringPhrase(Phrase):
    id = "string"

    def __init__(self):
        super().__init__()
        self.add_subs(_backslash_phrase)

    class NodeToken(NodeToken):
        id = "string-quotes"

    class TDefaultToken(Token):
        id = "string-content"

    debug.html_server.token_css[NodeToken] = "color: green; font-weight: bold;"
    debug.html_server.token_css[TDefaultToken] = "color: green;"

    def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
        if m := re.search("([frbu]{0,2})('''|\"\"\"|'|\")", stream.unparsed, re.IGNORECASE):
            if p := m.group(1).lower():
                if "f" in p:
                    return self.NodeToken(m.start(), m.end(), SwitchTo(_fstring_phrase("r" in p)), quotes=m.group(2))
                elif "b" in p:
                    return self.NodeToken(m.start(), m.end(), SwitchTo(_bstring_phrase("r" in p)), quotes=m.group(2))
                elif "r" in p:
                    return self.NodeToken(m.start(), m.end(), SwitchTo(_rstring_phrase), quotes=m.group(2))
            return self.NodeToken(m.start(), m.end(), quotes=m.group(2))

    def ends(self, stream: Stream) -> EndToken | None:
        if m := re.search(stream.node.extras.quotes, stream.unparsed):
            return EndToken(m.start(), m.end(), LStrip(len(m.group()[1:])))


_string_phrase = StringPhrase()


class RStringPhrase(StringPhrase):
    id = "rstring"


_rstring_phrase = RStringPhrase()


class FStringPhrase(StringPhrase):
    id = "fstring"

    class FStringFormatContentPhrase(Phrase):
        id = "fstring-content-format"

        class NodeToken(NodeToken):
            id = "fstring-content-format-open"

        class EndToken(EndToken):
            id = "fstring-content-format-close"

        debug.html_server.token_css[NodeToken] = "color: #e6c17e;"
        debug.html_server.token_css[EndToken] = "color: #e6c17e;"

        def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
            if m := re.search("\\{", stream.unparsed):
                return self.NodeToken(m.start(), m.end())

        def ends(self, stream: Stream) -> EndToken | None:
            if m := re.search("}", stream.unparsed):
                return self.EndToken(m.start(), m.end())

    fstring_format_content_phrase = FStringFormatContentPhrase()

    class FStringFormatEscPhrase(Phrase):
        id = "fstring-format-esc"

        class NodeToken(NodeToken):
            id = "fstring-format-esc"

        debug.html_server.token_css[NodeToken] = "color: orange;"

        def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
            if m := re.search("\\{\\{", stream.unparsed):
                return self.NodeToken(m.start(), m.end())

        def ends(self, stream: Stream) -> EndToken | None:
            return InstantEndToken()

    fstring_format_esc_phrase = FStringFormatEscPhrase()

    def __init__(self):
        super().__init__()
        self.add_subs(self.fstring_format_content_phrase, self.fstring_format_esc_phrase)

    def __call__(self, r: bool):
        new = super().__call__()
        new.tokenize = _rstring_phrase.tokenize if r else _string_phrase.tokenize
        return self


_fstring_phrase = FStringPhrase()


class BStringPhrase(StringPhrase):
    id = "bstring"

    class TDefaultToken(Token):
        id = "bstring-content"

    debug.html_server.token_css[TDefaultToken] = "color: yellow;"

    def __call__(self, r: bool):
        new = super().__call__()
        new.tokenize = _rstring_phrase.tokenize if r else _string_phrase.tokenize
        return self


_bstring_phrase = BStringPhrase()


class NumberPhrase(Phrase):
    id = "number"

    class Token(Token):
        id = "number"

    debug.html_server.token_css[Token] = "color: cyan;"

    def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
        if m := re.search("\\.?\\d[\\d_.e+-]*j?", stream.unparsed, re.IGNORECASE):
            return NodeToken(m.start(), m.end(), RTokenize(len(m.group())))

    def tokenize(
            self,
            stream: TokenizeStream,
    ) -> Type[Token] | Callable[[int, str], Token]:
        stream.eat_remain()
        return self.Token


_number_phrase = NumberPhrase()


class VariablePhrase(Phrase):
    id = "variable"

    class KeywordToken(Token):
        id = "keyword"

    class SoftKeywordToken(Token):
        id = "soft-keyword"

    class BuiltinToken(Token):
        id = "builtin"

    class VariableToken(Token):
        id = "variable"

    debug.html_server.token_css[KeywordToken] = "color: orange;"
    debug.html_server.token_css[SoftKeywordToken] = "color: orange;"
    debug.html_server.token_css[BuiltinToken] = "color: blue;"

    def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
        if m := re.search("[_a-zA-Z]\\w*", stream.unparsed):
            return NodeToken(m.start(), m.end(), RTokenize(len(m.group())))

    _kwlist = keyword.kwlist
    _softkwlist = keyword.softkwlist
    _builtins = dir(builtins)

    def tokenize(self, stream: TokenizeStream) -> Type[Token] | Callable[[int, str, Stream, NodeToken], Type[Token]]:
        token = stream.eat_remain()
        if token in self._kwlist:
            return self.KeywordToken
        elif token in self._softkwlist:
            return self.SoftKeywordToken
        elif token in self._builtins:
            return self.BuiltinToken
        else:
            return self.VariableToken

    def ends(self, stream: Stream) -> EndToken | None:
        return InstantEndToken()


_variable_phrase = VariablePhrase()


class AttributePhrase(Phrase):
    id = "attribute"

    class Token(Token):
        id = "attribute"

    def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
        if m := re.search("(\\s*)\\.(\\s*\\w+)", stream.unparsed):
            return NodeToken(m.start(), m.end(), LStrip(len(m.group(1))) | RTokenize(len(m.group(2))))

    def tokenize(self, stream: TokenizeStream) -> Type[Token] | Callable[[int, str, Stream, NodeToken], Type[Token]]:
        stream.eat_remain()
        return self.Token


_attribute_phrase = AttributePhrase()


class BracketPhrase(Phrase):
    id = "bracket"

    class Token(Token):
        id = "bracket"

    def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
        if m := re.search("[\\[({]", stream.unparsed):
            return NodeToken(m.start(), m.end(), close={
                "[": re.compile("]"),
                "(": re.compile("\\)"),
                "{": re.compile("}"),
            }[m.group()])

    def ends(self, stream: Stream) -> EndToken | None:
        if m := stream.node.extras.close.search(stream.unparsed):
            return EndToken(m.start(), m.end())


_bracket_phrase = BracketPhrase()


class CallPhrase(Phrase):
    id = "call"

    class Token(Token):
        id = "call"

    def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
        if m := re.search("\\(", stream.unparsed):
            return NodeToken(m.start(), m.end())

    def ends(self, stream: Stream) -> EndToken | None:
        if m := re.search("\\)", stream.unparsed):
            return EndToken(m.start(), m.end())


_call_phrase = CallPhrase()


PRIME_PHRASES = {
    comment_phrase,
    _string_phrase,
    _number_phrase,
    _variable_phrase,
    _bracket_phrase,
}


class DecoratorPhrase(Phrase):
    id = "decorator"

    class NodeToken(NodeToken):
        id = "decorator-operator"

    class Token(Token):
        id = "decorator-name"

    debug.html_server.token_css[NodeToken] = "color: yellow; font-weight: bold;"
    debug.html_server.token_css[Token] = "color: yellow;"

    def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
        if stream.viewpoint == 0:
            if m := re.search("@(\\w+)", stream.unparsed):
                return self.NodeToken(m.start(), m.end(), RTokenize(len(m.group(1))))

    def tokenize(self, stream: TokenizeStream) -> Type[Token] | Callable[[int, str], Token]:
        if stream.context == "n":
            stream.eat_remain()
            return self.Token
        else:
            stream.eat_remain()
            return Token

    def ends(self, stream: Stream) -> EndToken | None:
        if stream.viewpoint == 0:
            if re.search("^\\s*class|def|@", stream.row):
                return InstantEndToken()


decorator_phrase = DecoratorPhrase()


class ConstructorPhrase(Phrase):
    id = "constructor"

    class NodeToken(NodeToken):
        id = "constructor-start"

    class EndToken(EndToken):
        id = "constructor-end"

    debug.html_server.token_css[NodeToken] = "color: #b1b1fb; font-weight: bold;"

    class InnerPhrase(Phrase):
        id = "constructor-inner"

        class CloseToken(EndToken):
            id = "constructor-close"

        debug.html_server.token_css[CloseToken] = "color: #b1b1fb; font-weight: bold;"

        def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
            return NodeToken(0, 0)

        def ends(self, stream: Stream) -> EndToken | InstantEndToken | None:
            try:
                i = stream.unparsed.index(")")
                return self.CloseToken(i, i + 1)
            except ValueError:
                return None

    inner_phrase = InnerPhrase()

    class ReturnHintPhrase(Phrase):
        id = "constructor-return-hint"

        class NodeToken(NodeToken):
            id = "constructor-return-hint"

        def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
            if m := re.search("\\s*->\\s*", stream.unparsed):
                return self.NodeToken(m.start(), m.end())

        def ends(self, stream: Stream) -> EndToken | InstantEndToken | None:
            try:
                i = stream.unparsed.index(":")
                return EndToken(i, i + 1)
            except ValueError:
                return None

    return_hint_phrase = ReturnHintPhrase()

    def __init__(self):
        super().__init__()
        self.add_subs(self.return_hint_phrase)
        self.inner_phrase.add_subs(PRIME_PHRASES)
        self.return_hint_phrase.add_subs(PRIME_PHRASES)

    def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
        if m := re.search("\\(", stream.unparsed):
            return self.NodeToken(m.start(), m.end(), ForwardTo(self.inner_phrase))

    def ends(self, stream: Stream) -> EndToken | None:
        if m := re.search("\\s*:", stream.unparsed):
            return self.EndToken(m.start(), m.end())


_constructor_phrase = ConstructorPhrase()


class FunctionPhrase(Phrase):
    id = "function"

    class NodeToken(NodeToken):
        id = "function-keyword"

    debug.html_server.token_css[NodeToken] = "color: orange; font-weight: bold;"

    class FunkNameToken(Token):
        id = "function-name"

    debug.html_server.token_css[FunkNameToken] = "border-bottom: 1px solid orange; font-weight: bold;"

    def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
        if stream.viewpoint == 0:
            if m := re.search("^(\\s*)(def\\s+)(\\w+\\s*)", stream.row):
                return self.NodeToken(m.start(), m.end(), RTokenize(len(m.group(3))) | ForwardTo(_constructor_phrase), indent=len(m.group(1)))

    def ends(self, stream: Stream) -> EndToken | None:
        if stream.viewpoint == 0:
            if (m := re.search("^ *(?=.)", stream.row)) and len(m.group()) <= stream.node.extras.indent:
                return InstantEndToken()

    def tokenize(self, stream: TokenizeStream) -> Type[Token] | Callable[[int, str, Stream, NodeToken], Type[Token]]:
        if stream.context == "n":
            stream.eat_remain()
            return self.FunkNameToken
        else:
            stream.eat_remain()
            return Token


function_phrase = FunctionPhrase()


class ClassPhrase(Phrase):
    id = "class"

    class NodeToken(NodeToken):
        id = "class-keyword"
        indent: int

    debug.html_server.token_css[NodeToken] = "color: orange; font-weight: bold;"

    class ClassNameToken(Token):
        id = "class-name"

    debug.html_server.token_css[ClassNameToken] = "border-bottom: 1px solid orange; font-weight: bold;"

    class ClassInheritToken(Token):
        id = "class-inherit"

    def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
        if stream.viewpoint == 0:
            if m := re.search("^(\\s*)(class\\s+)(\\w+\\s*)", stream.row):
                return self.NodeToken(m.start(), m.end(), RTokenize(len(m.group(3))) | ForwardTo(_constructor_phrase), indent=len(m.group(1)))

    def ends(self, stream: Stream) -> EndToken | None:
        if stream.viewpoint == 0:
            if (m := re.search("^ *(?=.)", stream.row)) and len(m.group()) <= stream.node.extras.indent:
                return InstantEndToken()

    def tokenize(self, stream: TokenizeStream) -> Type[Token] | Callable[[int, str, Stream, NodeToken], Type[Token]]:
        if stream.context == "n":
            stream.eat_remain()
            return self.ClassNameToken
        else:
            stream.eat_remain()
            return Token


class_phrase = ClassPhrase()


#####################################################################################################
# MAIN

def main():
    main = Root()

    main.add_subs(
        PRIME_PHRASES,
        class_phrase,
        function_phrase,
        decorator_phrase,
    )

    decorator_phrase.add_suffixes(decorator_phrase, function_phrase, class_phrase)
    decorator_phrase.add_subs(_call_phrase, _attribute_phrase, comment_phrase)
    function_phrase.add_subs(main.__sub_phrases__)

    _bracket_phrase.add_subs(PRIME_PHRASES)
    _call_phrase.add_subs(PRIME_PHRASES)
    _call_phrase.add_suffixes(_attribute_phrase)
    _attribute_phrase.add_suffixes(_call_phrase)
    _variable_phrase.add_suffixes(_attribute_phrase, _call_phrase)

    class_phrase.add_subs(main.__sub_phrases__)
    _fstring_phrase.fstring_format_content_phrase.add_subs(main.__sub_phrases__)

    return main
