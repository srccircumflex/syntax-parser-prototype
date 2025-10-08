from src.syntax_parser_prototype import *
from src.syntax_parser_prototype.features.tokenize import *

import re


LStrip | SwitchTo | SwitchPh | RTokenize | ForwardTo


class _P1(Phrase):
    id = "p1"

    class TDefaultToken(Token):
        id = "p1-content"

    class NodeToken(NodeToken):
        id = "p1-start"

    class P1Mask(Phrase):
        id = "p1-mask"

        class TDefaultToken(Token):
            id = "p1-mask-content"

        class NodeToken(NodeToken):
            id = "p1-mask-start"

        def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
            if m := re.search("#§", stream.unparsed):
                return MaskToken(m.start(), m.end())
            if m := re.search("#>", stream.unparsed):
                return MaskNodeToken(m.start(), m.end())
            return None

        def ends(self, stream: Stream) -> EndToken | None:
            if m := re.search("<#", stream.unparsed):
                return EndToken(m.start(), m.end())
            return None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_subs(self.P1Mask())

    def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
        if m := re.search("§1start", stream.unparsed):
            return self.NodeToken(m.start(), m.end(), RTokenize(len(m.group()) - 1))
        if m := re.search("§forward to 4 from root", stream.unparsed):
            return self.NodeToken(m.start(), m.end(), RTokenize(len(m.group()) - 1) | ForwardTo(P4))
        return None

    def ends(self, stream: Stream):
        if m := re.search("§1end", stream.unparsed):
            return EndToken(m.start(), m.end())
        return None


P1 = _P1()


class _P4(Phrase):
    id = "p4"

    class TDefaultToken(Token):
        id = "p4-content"

    def starts(self, stream: Stream):
        if m := re.search("at end of 3", stream.unparsed):
            # from 3
            return NodeToken(m.start(), m.end())
        if m := re.search("at start of 1", stream.unparsed):
            # from root
            return NodeToken(m.start(), m.end())
        return None

    def ends(self, stream: Stream):
        if m := re.search("\\s§4end", stream.unparsed):
            return EndToken(m.start(), m.end(), LStrip(1))
        return None


P4 = _P4()


class _P3(Phrase):
    id = "p3"

    class TDefaultToken(Token):
        id = "p3-content"

    def starts(self, stream: Stream):
        if m := re.search("§3start", stream.unparsed):
            return NodeToken(m.start(), m.end())

    def ends(self, stream: Stream):
        if m := re.search("§forward to 4 at 3", stream.unparsed):
            at = m.start()
            return EndToken(at, at + 1, ForwardTo(P4))
        if m := re.search("§3end", stream.unparsed):
            at = m.start()
            return EndToken(at, at + 1)


P3 = _P3()


class _P2(Phrase):
    id = "p2"

    class TDefaultToken(Token):
        id = "p2-content"

    def starts(self, stream: Stream) -> NodeToken | Token | MaskToken | MaskNodeToken | None:
        if m := re.search("§switch to 3 at 2", stream.unparsed):
            return Token(m.start(), m.end(), LStrip(1) | SwitchTo(P3))
        if m := re.search("§Istart", stream.unparsed):
            return InstantNodeToken(m.start(), m.end())
        if m := re.search("§2start", stream.unparsed):
            return NodeToken(m.start(), m.end(), SwitchTo(P3))
        if m := re.search("(§switch ph at 2)start", stream.unparsed):
            return NodeToken(m.start(), m.end(1), SwitchPh(P2))

    def ends(self, stream: Stream):
        if m := re.search("11 22 33 44 55 §2end aa bb cc dd ee", stream.unparsed):
            return EndToken(
                m.start(), m.end(),
                SwitchTo(P1) | LStrip(3) |
                SwitchTo(P2) | LStrip(3) |
                SwitchTo(P3) | LStrip(3) |
                SwitchTo(P4) | LStrip(3) |
                SwitchTo(MAIN) | LStrip(3) |
                SwitchTo(P1) | RTokenize(3) |
                SwitchTo(P2) | RTokenize(3) |
                SwitchTo(P3) | RTokenize(3) |
                SwitchTo(P4) | RTokenize(3) |
                SwitchTo(MAIN) | RTokenize(3)
            )
        return None


P2 = _P2()


P1.add_subs(P2)
P3.add_subs(P2)


template = """\
 1~ §1start                                         @1 ~
 2~ masking -> #§1end #> §1end <#                   @1 ~
 3~ lstrip '§´ -> §switch to 3 at 2 as standalone   @3 ~
 4~ §forward to 4 at 3 at end of 3                  @4 ~
 5~ §4end                                           @0 ~
 6~ §forward to 4 from root at start of 1 §4end     @1 ~
 7~ §1end                                           @0 ~
 8~ §1start §Istart <- instand form root            @2 ~
 9~ 11 22 33 44 55 §2end aa bb cc dd ee             @0 ~
10~ §2start switch to 3                             @3 ~
11~ §3end ... §3start <- will be node of 2 (content @2 ~
12~ remains 3) §switch ph at 2start to 2            @2 ~
"""


if __name__ == "__main__":
    MAIN = Root()
    MAIN.add_subs(P1, P2, P3)

    result = MAIN.parse_string(template)

    assert template == result.tokenReader.branch.content

    from src.syntax_parser_prototype import debug

    debug.html_server.main_css += "pre { font-family: monospace; background-color: #999; padding: 10px;}"
    debug.html_server.token_css[_P1.TDefaultToken] = "background-color: yellow;  /*border-bottom: 1px solid yellow  */"
    debug.html_server.token_css[_P2.TDefaultToken] = "background-color: cyan;    /*border-bottom: 1px solid cyan    */"
    debug.html_server.token_css[_P3.TDefaultToken] = "background-color: green;   /*border-bottom: 1px solid green   */"
    debug.html_server.token_css[_P4.TDefaultToken] = "background-color: orange;  /*border-bottom: 1px solid orange  */"

    debug.html_server(result)

