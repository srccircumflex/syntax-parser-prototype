from __future__ import annotations

import builtins
import keyword
import re
import abc
from re import compile, Pattern
from typing import Any, Type, Callable, overload

from src.syntax_parser_prototype import *
from src.syntax_parser_prototype import visualisation

builtins.id(re.compile("a")  . search("a".lower(), 0, endpos=1))

r"raw string"

A = [
    3.14,
    10.,
    .001,
]

B = (
    1e100,
    3.14e-10,
    0e0,
    3.14_15_93,
)

C = {
    3.14j,
    10.j,
    10j,
}

D = {
    '''A''': .001j,
    br'bytes\\': 1e100j,
    f"""formatted {id(f'{Any}')} string""": 3.14e-10j,
    " \N{NULL} \000 \x00 \u0000 \U00000000 \" ": 3.14_15_93j,
}


class AClass:
    ...


class Class(abc.ABC, metaclass=abc.ABCMeta):

    @property
    @abc.abstractmethod
    def a(self):
        pass

    def __init__(self):
        self.b = 1


def func(a: int = (), b: str = "a", *c: Class, d: dict[str, int] = None, **e: int) -> None:

    def func2():
        pass

    class C:
        pass

    c = C()

    return None


class BackslashEscPhrase(Phrase):
    id = "backslash-esc"

    class Token(Token):
        id = "backslash-esc"

    def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
        if m := re.search("\\\\(N\\{\\w+}|\\d{3}|x[a-fA-F0-9]{2}|u\\d{4}|U\\d{8}|(.))", stream.unparsed, re.DOTALL):
            return self.Token(m.start(), m.group())


_backslash_phrase = BackslashEscPhrase()


class StringPhrase(Phrase):
    id = "string"

    def __init__(self):
        super().__init__()
        self.add_phrases(_backslash_phrase)

    class NodeToken(NodeToken):
        id = "string-quotes"

    class TNullToken(Token):
        id = "string-content"

    def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
        if m := re.search("([frbu]{0,2})('''|\"\"\"|'|\")", stream.unparsed, re.IGNORECASE):
            if p := m.group(1).lower():
                if "f" in p:
                    return self.NodeToken(m.start(), m.group(), switchto=_fstring_phrase("r" in p), quotes=m.group(2))
                elif "b" in p:
                    return self.NodeToken(m.start(), m.group(), switchto=_bstring_phrase("r" in p), quotes=m.group(2))
                elif "r" in p:
                    return self.NodeToken(m.start(), m.group(), switchto=_rstring_phrase, quotes=m.group(2))
            return self.NodeToken(m.start(), m.group(), quotes=m.group(2))

    def ends(self, stream: Stream) -> EndToken | None:
        if m := re.search(stream.node.extras.quotes, stream.unparsed):
            return EndToken(m.start(), stream.node.extras.quotes)


_string_phrase = StringPhrase()


class RStringPhrase(StringPhrase):
    id = "rstring"


_rstring_phrase = RStringPhrase()


class FStringPhrase(StringPhrase):
    id = "fstring"

    class FStringFormatContentPhrase(Phrase):
        id = "fstring-content-format"

        class NodeToken(NodeToken):
            id = "fstring-content-format"

        def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
            if m := re.search("\\{", stream.unparsed):
                return self.NodeToken(m.start(), m.group())

        def ends(self, stream: Stream) -> EndToken | None:
            if m := re.search("}", stream.unparsed):
                return EndToken(m.start(), m.group())

    fstring_format_content_phrase = FStringFormatContentPhrase()

    class FStringFormatEscPhrase(Phrase):
        id = "fstring-format-esc"

        class NodeToken(NodeToken):
            id = "fstring-format-esc"

        def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
            if m := re.search("\\{\\{", stream.unparsed):
                return self.NodeToken(m.start(), m.group())

        def ends(self, stream: Stream) -> EndToken | None:
            return XEndToken()

    fstring_format_esc_phrase = FStringFormatContentPhrase()

    def __init__(self):
        super().__init__()
        self.add_phrases(self.fstring_format_content_phrase, self.fstring_format_esc_phrase)

    def __call__(self, r: bool):
        new = super().__call__()
        new.tokenize = _rstring_phrase.tokenize if r else _string_phrase.tokenize
        return self


_fstring_phrase = FStringPhrase()


class BStringPhrase(StringPhrase):
    id = "bstring"

    def __call__(self, r: bool):
        new = super().__call__()
        new.tokenize = _rstring_phrase.tokenize if r else _string_phrase.tokenize
        return self


_bstring_phrase = BStringPhrase()


class NumberPhrase(Phrase):
    id = "number"

    class Token(Token):
        id = "number"

    def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
        if m := re.search("\\.?\\d[\\d_.e+-]*j?", stream.unparsed, re.IGNORECASE):
            return NodeToken(m.start(), "", tokenize=m.group())

    def tokenize(
            self,
            stream: TokenizeStream,
            n: int,
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

    def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
        if m := re.search("[_a-zA-Z]\\w*", stream.unparsed):
            return NodeToken(m.start(), "", tokenize=m.group())

    _kwlist = keyword.kwlist
    _softkwlist = keyword.softkwlist
    _builtins = dir(builtins)

    def tokenize(self, stream: TokenizeStream, n: int) -> Type[Token] | Callable[[int, str, Stream, NodeToken], Type[Token]]:
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
        return XEndToken()


_variable_phrase = VariablePhrase()


class AttributePhrase(Phrase):
    id = "attribute"

    class Token(Token):
        id = "attribute"

    def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
        if m := re.search("(\\s*)\\.(\\s*\\w+)", stream.unparsed):
            return NodeToken(m.start(), ".", lstrip=m.group(1), tokenize=m.group(2))

    def tokenize(self, stream: TokenizeStream, n: int) -> Type[Token] | Callable[[int, str, Stream, NodeToken], Type[Token]]:
        stream.eat_remain()
        return self.Token


_attribute_phrase = AttributePhrase()


class BracketPhrase(Phrase):
    id = "bracket"

    class Token(Token):
        id = "bracket"

    def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
        if m := re.search("[\\[({]", stream.unparsed):
            return NodeToken(m.start(), m.group(), close={
                "[": re.compile("]"),
                "(": re.compile("\\)"),
                "{": re.compile("}"),
            }[m.group()])

    def ends(self, stream: Stream) -> EndToken | None:
        if m := stream.node.extras.close.search(stream.unparsed):
            return EndToken(m.start(), m.group())


_bracket_phrase = BracketPhrase()


class CallPhrase(Phrase):
    id = "call"

    class Token(Token):
        id = "call"

    def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
        if m := re.search("\\(", stream.unparsed):
            return NodeToken(m.start(), "(")

    def ends(self, stream: Stream) -> EndToken | None:
        if m := re.search("\\)", stream.unparsed):
            return EndToken(m.start(), ")")


_call_phrase = CallPhrase()


PRIME_PHRASES = {
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

    def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
        if stream.viewpoint == 0:
            if m := re.search("@(\\w+)", stream.unparsed):
                return self.NodeToken(m.start(), "@", tokenize=m.group(1))

    def tokenize(self, stream: TokenizeStream, n: int) -> Type[Token] | Callable[[int, str], Token]:
        if stream.context == "n":
            stream.eat_remain()
            return self.Token
        else:
            stream.eat_remain()
            return Token

    def ends(self, stream: Stream) -> EndToken | None:
        if stream.viewpoint == 0:
            if re.search("^\\s*class|def|@", stream.row):
                return XEndToken()


decorator_phrase = DecoratorPhrase()


class ConstructorPhrase(Phrase):
    id = "constructor"

    class NodeToken(NodeToken):
        id = "constructor-start"

    class EndToken(EndToken):
        id = "constructor-end"

    class InnerPhrase(Phrase):
        id = "constructor-inner"

        class CloseToken(EndToken):
            id = "constructor-close"

        def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
            return NodeToken(0, "")

        def ends(self, stream: Stream) -> EndToken | XEndToken | None:
            try:
                return self.CloseToken(stream.unparsed.index(")"), ")")
            except ValueError:
                return None

    inner_phrase = InnerPhrase()

    class ReturnHintPhrase(Phrase):
        id = "constructor-return-hint"

        class NodeToken(NodeToken):
            id = "constructor-return-hint"

        def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
            if m := re.search("\\s*->\\s*", stream.unparsed):
                return self.NodeToken(m.start(), m.group())

        def ends(self, stream: Stream) -> EndToken | XEndToken | None:
            try:
                return EndToken(stream.unparsed.index(":"), "")
            except ValueError:
                return None

    return_hint_phrase = ReturnHintPhrase()

    def __init__(self):
        super().__init__()
        self.add_phrases(self.return_hint_phrase)
        self.inner_phrase.add_phrases(PRIME_PHRASES)
        self.return_hint_phrase.add_phrases(PRIME_PHRASES)

    def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
        if m := re.search("\\(", stream.unparsed):
            return self.NodeToken(m.start(), "(", forwardto=self.inner_phrase)

    def ends(self, stream: Stream) -> EndToken | None:
        if m := re.search("\\s*:", stream.unparsed):
            return self.EndToken(m.start(), m.group())


_constructor_phrase = ConstructorPhrase()


class FunctionPhrase(Phrase):
    id = "function"

    class NodeToken(NodeToken):
        id = "function-keyword"

    class FunkNameToken(Token):
        id = "function-name"

    def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
        if stream.viewpoint == 0:
            if m := re.search("^(\\s*)(def\\s+)(\\w+\\s*)(\\()", stream.row):
                return self.NodeToken(m.start(), m.group(1) + m.group(2), tokenize=m.group(3), forwardto=_constructor_phrase, indent=len(m.group(1)))

    def ends(self, stream: Stream) -> EndToken | None:
        if stream.viewpoint == 0:
            if (m := re.search("^ *(?=.)", stream.row)) and len(m.group()) <= stream.node.extras.indent:
                return XEndToken()

    def tokenize(self, stream: TokenizeStream, n: int) -> Type[Token] | Callable[[int, str, Stream, NodeToken], Type[Token]]:
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

    class ClassNameToken(Token):
        id = "class-name"

    class ClassInheritToken(Token):
        id = "class-inherit"

    def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
        if stream.viewpoint == 0:
            if m := re.search("^(\\s*)(class\\s+)(\\w+\\s*)(\\(?)", stream.row):
                return self.NodeToken(m.start(), m.group(1) + m.group(2), tokenize=m.group(3), forwardto=_constructor_phrase, indent=len(m.group(1)))

    def ends(self, stream: Stream) -> EndToken | None:
        if stream.viewpoint == 0:
            if (m := re.search("^ *(?=.)", stream.row)) and len(m.group()) <= stream.node.extras.indent:
                return XEndToken()

    def tokenize(self, stream: TokenizeStream, n: int) -> Type[Token] | Callable[[int, str, Stream, NodeToken], Type[Token]]:
        if stream.context == "n":
            stream.eat_remain()
            return self.ClassNameToken
        else:
            stream.eat_remain()
            return Token


class_phrase = ClassPhrase()

######################################################


main = MainPhrase()

main.add_phrases(
    PRIME_PHRASES,
    class_phrase,
    function_phrase,
    decorator_phrase,
)

decorator_phrase.add_suffix_phrases(decorator_phrase, function_phrase, class_phrase)
decorator_phrase.add_phrases(_call_phrase, _attribute_phrase)
function_phrase.add_phrases(main.__sub_phrases__)

_bracket_phrase.add_phrases(PRIME_PHRASES)
_call_phrase.add_phrases(PRIME_PHRASES)
_call_phrase.add_suffix_phrases(_attribute_phrase)
_attribute_phrase.add_suffix_phrases(_call_phrase)
_variable_phrase.add_suffix_phrases(_attribute_phrase, _call_phrase)


class_phrase.add_phrases(main.__sub_phrases__)

_fstring_phrase.fstring_format_content_phrase.add_phrases(main.__sub_phrases__)


with open(__file__) as f:
    content = f.read()
    result = main.parse_string(content)

result_content = str().join(i.content for i in result.gen_branch())

with open(__file__ + ".out", "w") as f:
    f.write(result_content)

print(result_content == content)

# print(root.__repr__())
# print(result.__repr__())
# print(visualisation.pretty_xml_result(result))

visualisation.html_server(result)
# visualisation.start_structure_graph_app(root)
