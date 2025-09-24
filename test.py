from __future__ import annotations

from re import compile, Pattern

from syntax_parser_prototype import *
from syntax_parser_prototype import visualisation


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

    def starts(self, stream: Stream, branch: Branch) -> Branch | Token | None:
        if m := self.start_pattern.search(stream.unparsed):
            if self.stop_pattern:
                return Branch(m.start(), m.group(), stream, branch, self)
            else:
                return Token(m.start(), m.group(), stream, branch)
        else:
            return None

    def ends(self, stream: Stream) -> NodeToken | None:
        if m := self.stop_pattern.search(stream.unparsed):
            return NodeToken(m.start(), m.group(), stream, stream.branch)
        else:
            return None


root = RootPhrase(id="#root")

_bracket = SimpleRegexPhrase(compile('\\('), compile('\\)'), id="bracket").add_self()
_funcall = SimpleRegexPhrase(compile('\\w+\\s*\\('), compile('\\)'), id="function")
_consoleline = SimpleRegexPhrase(compile('>>>'), compile('$'), id="consoleline").add_phrases(_funcall)
_variable = SimpleRegexPhrase(compile('\\w+(?!\\s*\\()'), stop_pattern=None, id="variable")
_operation = SimpleRegexPhrase(compile('[-+*/]'), stop_pattern=None, id="operation")
_curly_brackets = SimpleRegexPhrase(compile("\\{"), compile("}"), id="curly brackets")
_string_a = SimpleRegexPhrase(compile("'"), compile("'"), id="string").add_phrases(_curly_brackets)
_string_b = SimpleRegexPhrase(compile('"'), compile('"'), id="string").add_phrases(_curly_brackets)
_angular_brackets = SimpleRegexPhrase(compile("\\["), compile("]"), id="angular brackets")
_string_b.add_suffix_phrases(_angular_brackets)
_bracket.add_phrases(_variable, _operation, _string_a, _string_b, _funcall)
root.add_phrases(_bracket, _variable, _operation, _string_a, _string_b, _consoleline)
_consoleline.add_phrases(root.__sub_phrases__)
_consoleline.__sub_phrases__.discard(_consoleline)
_funcall.add_phrases(root.__sub_phrases__)
result = root.parse_string("""\
>>> prettyprint('( (a * b / (c + a)) * (b / (c – a) * b) / c ) + a')
(
   (
       a * b / (c + a)
   ) * (
       b / (c – a) * b
   ) / c 
) + a

>>> int("42"[1:3] + "3") + 19
42
""")

visualisation.html_on_server(result)

#visualisation.start_structure_graph_app(root)

#print(visualisation.pretty_xml_result(result))
