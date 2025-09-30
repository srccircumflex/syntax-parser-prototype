from __future__ import annotations

import re
from re import compile, Pattern
from typing import Any, Type, Callable

from src.syntax_parser_prototype import *
from src.syntax_parser_prototype import visualisation


class BSMaskPhrase(Phrase):

    class Token(Token):
        xml_label = "BSM"

    def __init__(self):
        Phrase.__init__(self)
        self.id = "\\"

    def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
        try:
            i = stream.unparsed.index("\\")
            return MaskToken(i, stream.unparsed[i:i + 2])
        except ValueError:
            return None


class SimpleRegexPhrase(Phrase):

    def __init__(
            self,
            start_pattern: Pattern[str],
            stop_pattern: Pattern[str] | None = None,
            id: Any = ""
    ):
        Phrase.__init__(self)
        self.id = id
        self.start_pattern = start_pattern
        self.stop_pattern = stop_pattern
        self.add_phrases(BSMaskPhrase())

    def starts(self, stream: Stream) -> NodeToken | Token | None:
        if m := self.start_pattern.search(stream.unparsed):
            if self.stop_pattern:
                return NodeToken(m.start(), m.group())
            else:
                return Token(m.start(), m.group())
        else:
            return None

    def tokenize(self, stream: TokenizeStream, n) -> Type[Token] | Callable[[int, str, Stream, NodeToken], Type[Token]]:
        if stream.eat_n(1) == "\\":
            stream.eat_n(1)
            return BSMaskPhrase.Token
        else:
            stream.eat_until(re.compile("\\\\"))
            return Token

    def ends(self, stream: Stream) -> EndToken | None:
        if m := self.stop_pattern.search(stream.unparsed):
            return EndToken(m.start(), m.group())
        else:
            return None


class MaskBranchPhrase(Phrase):

    def __init__(self):
        Phrase.__init__(self)
        self.id = "¿"

    def starts(self, stream: Stream) -> NodeToken | Token | None:
        try:
            i = stream.unparsed.index("¿")
            return MaskNodeToken(i, stream.unparsed[i])
        except ValueError:
            return None

    def ends(self, stream: Stream) -> EndToken | None:
        try:
            i = stream.unparsed.index("¿")
            return EndToken(i, stream.unparsed[i])
        except ValueError:
            return None


root = MainPhrase()

_bracket = SimpleRegexPhrase(compile('\\('), compile('\\)'), id="bracket").add_self()
_funcall = SimpleRegexPhrase(compile('\\w+\\s*\\('), compile('\\)'), id="function")
_consoleline = SimpleRegexPhrase(compile('>>>'), compile('$'), id="console line").add_phrases(_funcall)
_variable = SimpleRegexPhrase(compile('\\w+(?!\\s*\\()'), stop_pattern=None, id="variable")
_operation = SimpleRegexPhrase(compile('[-+*/]'), stop_pattern=None, id="operation")
_curly_brackets = SimpleRegexPhrase(compile("\\{"), compile("}"), id="curly brackets")
_string_a = SimpleRegexPhrase(compile("'"), compile("'"), id="string-a").add_phrases(_curly_brackets,
                                                                                     MaskBranchPhrase()
                                                                                     )
_string_b = SimpleRegexPhrase(compile('"'), compile('"'), id="string-b").add_phrases(_curly_brackets)
_angular_brackets = SimpleRegexPhrase(compile("\\["), compile("]"), id="angular brackets")
_string_b.add_suffix_phrases(_angular_brackets)
_bracket.add_phrases(_variable, _operation, _string_a, _string_b, _funcall)
root.add_phrases(_bracket, _variable, _operation, _string_a, _string_b, _consoleline)
_consoleline.add_phrases(root.__sub_phrases__)
_consoleline.__sub_phrases__.discard(_consoleline)
_funcall.add_phrases(root.__sub_phrases__)
result = root.parse_string("""\
>>> prettyprint('( (a\\' * b / (c + a)) * (b / (c – a) * b) / c ) ¿ a')
(
   (
       a * b / (c + a)
   ) * (
       b / \\\\(c – a) * b
   ) / c 
    ¿  \\' ¿¿  ¿'''¿ ' ) + a

>>> int("42"[1:3] + "3") + 19
42
""")

# print(root.__repr__())
# print(result.__repr__())
# print(visualisation.pretty_xml_result(result))

visualisation.html_on_server.token_css[BSMaskPhrase.Token] = 'color: orange; font-weight: bold;'
visualisation.html_on_server(result)
# visualisation.start_structure_graph_app(root)


