from __future__ import annotations

import re
from re import compile, Pattern
from typing import Any, Type, Callable

from src.syntax_parser_prototype import *
from src.syntax_parser_prototype import visualisation
from src.syntax_parser_prototype.utils import NodeTokenizeFuture


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
            if m := re.search("^(\\s*)(class\\s+)(\\w+)((\\(.*:)|:)", stream.row):
                return self.NodeToken(m.start(), m.group(1) + m.group(2), tokenize=m.group(3) + m.group(4), indent=len(m.group(1)))

    def ends(self, stream: Stream) -> EndToken | None:
        if stream.viewpoint == 0:
            if (m := re.search("^ *(?=.)", stream.row)) and len(m.group()) <= stream.node.extras.indent:
                return EndToken(0, "")

    def tokenize(self, stream: TokenizeStream, n: int) -> Type[Token] | Callable[[int, str, Stream, NodeToken], Type[Token]]:
        if isinstance(stream.delimiter, NodeTokenizeFuture):
            if n == 0:
                stream.eat_until(re.compile("\\s*[(:]"))
                return self.ClassNameToken
            else:
                if (x := stream.eat_until(re.compile(":"))) and x[0] != " ":
                    return self.ClassInheritToken
                else:
                    stream.eat_n(1)  # :
                    return Token
        else:
            stream.eat_remain()
            return Token


class_phrase = ClassPhrase().add_self()


class StringPhrase(Phrase):
    id = "string"
    indent: int

    class NodeToken(NodeToken):
        id = "string-quotes"

    class TNullToken(Token):
        id = "string-content"

    def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
        if m := re.search("([fFrRbBuU]{0,2})('|'''|\"|\"\"\")", stream.unparsed):
            if p := m.group(1).lower():
                if "f" in p:
                    return self.NodeToken(m.start(), m.group(), goto=fstring_phrase("r" in p), quotes=m.group(2))
                elif "b" in p:
                    return self.NodeToken(m.start(), m.group(), goto=bstring_phrase("r" in p), quotes=m.group(2))
                elif "r" in p:
                    return self.NodeToken(m.start(), m.group(), goto=rstring_phrase, quotes=m.group(2))
                else:
                    return self.NodeToken(m.start(), m.group(), end=m.group(2))

    def ends(self, stream: Stream) -> EndToken | None:
        if m := re.search(stream.node.extras.quotes, stream.unparsed):
            return EndToken(m.start(), m.group()) 
    

string_phrase = StringPhrase()


class FStringPhrase(StringPhrase):
    id = "fstring"


fstring_phrase = FStringPhrase()








main = MainPhrase()


main.add_phrases(class_phrase)



with open(__file__) as f:
    result = main.parse_string(f.read())



# print(root.__repr__())
# print(result.__repr__())
# print(visualisation.pretty_xml_result(result))

visualisation.html_on_server(result)
# visualisation.start_structure_graph_app(root)

