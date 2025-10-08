# Represents a simplified method for parsing python syntax.
# The following paragraph is to be parsed:
#   foo = 42
#   baz = not f'{foo + 42 is foo} \' bar'

import keyword
import re

from src.syntax_parser_prototype import *
from src.syntax_parser_prototype.features.tokenize import *


# simple string definition
class StringPhrase(Phrase):
    id = "string"

    # token typing
    class NodeToken(NodeToken):
        id = "string-start-quotes"

    class Token(Token):
        id = "string-content"

    TDefaultToken = Token

    class EndToken(EndToken):
        id = "string-end-quotes"

    # backslash escape handling
    class MaskPhrase(Phrase):
        id = "mask"

        def starts(self, stream: Stream):
            if m := re.search("\\\\.", stream.unparsed):
                # baz = not f'{foo + 42 is foo} \' bar'
                #                               ↑ prevents closure
                return MaskToken(m.start(), m.end())
                # could also be implemented as a stand-alone token or 
                # independent phrase if the pattern is to be tokenized separately
            else:
                return None

    PH_MASK = MaskPhrase()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # creates the logic during initialization
        self.add_subs(self.PH_MASK)

    def starts(self, stream: Stream):
        # searches for quotation marks and possible prefix and saves the quotation mark type
        # switches to a different phase configuration if the f-string pattern is found
        if m := re.search("(f?)(['\"])", stream.unparsed, re.IGNORECASE):
            # baz = not f'{foo + 42 is foo} \' bar'
            #           ↑
            if prefix := m.group(1):
                switchto = PH_FSTRING
            else:
                switchto = self
            return self.NodeToken(m.start(), m.end(), SwitchTo(switchto), quotes=m.group(2))
        else:
            return None

    def ends(self, stream: Stream):
        # searches for the saved quotation mark type
        if m := re.search(stream.node.extras.quotes, stream.unparsed):
            # baz = not f'{foo + 42 is foo} \' bar'
            #                                     ↑
            return self.EndToken(m.start(), m.end())
        else:
            return None


# modified string definition for f-string pattern
class FstringPhrase(StringPhrase):
    id = "fstring"

    # format content handling
    class FstringFormatContentPhrase(Phrase):
        id = "fstring-format-content"

        # token typing
        class NodeToken(NodeToken):
            id = "fstring-format-content-open"

        class EndToken(EndToken):
            id = "fstring-format-content-close"

        def starts(self, stream: Stream):
            if m := re.search("\\{", stream.unparsed):
                # baz = not f'{foo + 42 is foo} \' bar'
                #             ↑
                return self.NodeToken(m.start(), m.end())
            else:
                return None

        def ends(self, stream: Stream):
            # baz = not f'{foo + 42 is foo} \' bar'
            #                             ↑
            if m := re.search("}", stream.unparsed):
                return self.EndToken(m.start(), m.end())
            else:
                return None

    PH_FSTRING_FORMAT_CONTENT = FstringFormatContentPhrase()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # creates the logic during initialization
        self.add_subs(self.PH_FSTRING_FORMAT_CONTENT)


NUMBER42 = list()


# simple word definition
class WordPhrase(Phrase):
    id = "word"

    # token typing
    class KeywordToken(Token):
        id = "keyword"

    class VariableToken(Token):
        id = "variable"

    class NumberToken(Token):
        id = "number"

    class WordNode(NodeToken):
        id = "word"

        def atConfirmed(self) -> None:
            assert not self.inner

        def atFeaturized(self) -> None:
            # collect 42 during the parsing process
            if self.inner[0].content == "42":
                NUMBER42.append(self[0])

    def starts(self, stream: Stream):
        if m := re.search("\\w+", stream.unparsed):
            # foo = 42
            # ↑     ↑
            # baz = not f'{foo + 42 is foo} \' bar'
            # ↑     ↑      ↑     ↑  ↑  ↑
            return self.WordNode(
                m.start(),
                m.end(),
                # forwards the content to tokenize
                RTokenize(len(m.group()))
            )
            # could also be implemented as a stand-alone token, 
            # but this way saves conditional queries if the token is not prioritized
        else:
            return None

    def tokenize(self, stream: TokenizeStream):
        token = stream.eat_remain()
        if token in keyword.kwlist:
            # baz = not f'{foo + 42 is foo} \' bar'
            #       ↑               ↑
            return self.KeywordToken
        elif re.match("^\\d+$", token):
            # foo = 42
            #       ↑
            # baz = not f'{foo + 42 is foo} \' bar'
            #                    ↑
            return self.NumberToken
        else:
            # foo = 42
            # ↑
            # baz = not f'{foo + 42 is foo} \' bar'
            # ↑            ↑           ↑
            return self.VariableToken

    def ends(self, stream: Stream):
        # end the phrase immediately without content after the start process
        # foo = 42
        #    ↑    ↑
        # baz = not f'{foo + 42 is foo} \' bar'
        #    ↑     ↑      ↑    ↑  ↑   ↑
        return super().ends(stream)  # return InstantEndToken()


MAIN = Root()
PH_STRING = StringPhrase()
PH_FSTRING = FstringPhrase()
PH_WORD = WordPhrase()

# MAIN SETUP
#  - configure the logic at the top level
MAIN.add_subs(PH_STRING, PH_WORD)
#  - recursive reference to the logic of the top level
PH_FSTRING.PH_FSTRING_FORMAT_CONTENT.add_subs(MAIN.__sub_phrases__)


if __name__ == "__main__":
    from demos.quickstart import template

    with open(template.__file__) as f:
        # foo = 42
        # baz = not f'{foo + 42 is foo} \' bar'
        #
        content = f.read()

    # parse the content
    result = MAIN.parse_string(content)

    if PROCESS_RESULT := True:
        # some result processing
        assert content == result.tokenReader.branch.content
        token = result.tokenIndex.get_token_at_coord(1, 19)
        assert token.content == "42"
        assert token.column_end == 21
        assert token.data_end == 30
        assert token.node.phrase.id == "word"
        assert token.next.next.next.next.content == "is"
        assert token.node.node[0].tokenReader.inner.content == "foo"

        assert isinstance(result, NodeToken)
        for inner_token in result:
            if isinstance(inner_token, NodeToken):
                assert isinstance(inner_token.inner, list)
                assert isinstance(inner_token.end, EndToken)
            else:
                assert not hasattr(inner_token, "inner")
        assert isinstance(result.end, EndToken) and isinstance(result.end, EOF)

        assert len(NUMBER42) == 2

    if DEBUG := True:
        # visualisation
        print(*(f"std.  repr: {t} {t!r}" for t in NUMBER42), sep="\n")

        from src.syntax_parser_prototype import debug

        print(*(f"debug repr: {t} {t!r}" for t in NUMBER42), sep="\n")

        debug.html_server.token_css[WordPhrase.KeywordToken] = "font-weight: bold;"
        debug.html_server.token_css[WordPhrase.NumberToken] = "color: blue; border-bottom: 1px dotted blue;"
        debug.html_server.token_css[StringPhrase.NodeToken] = "color: green;"
        debug.html_server.token_css[StringPhrase.Token] = "color: green;"
        debug.html_server.token_css[StringPhrase.EndToken] = "color: green;"
        debug.html_server.token_css[FstringPhrase.FstringFormatContentPhrase.NodeToken] = "color: orange;"
        debug.html_server.token_css[FstringPhrase.FstringFormatContentPhrase.EndToken] = "color: orange;"

        debug.html_server(result)
