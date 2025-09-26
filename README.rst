.. code-block::
    console

    python3 -m pip install syntax-parser-prototype --upgrade
    python3 -m pip install syntax-parser-prototype[visualisation] --upgrade

syntax-parser-prototype
#######################

Basic objects for the specific implementation of a syntax parser.

Object categories
=================

[.*]Token
    (Parsing result) single token

[.*]Branch
    (Parsing result) container for tokens

Root[.*]
    objects for the top level (not intended for modification)

Phrase
    configuration object whose behavior is to be implemented by modifying the class.

    The main behavior is implemented by the more detailed definition of the ``start`` and ``end`` methods.
    Additional predetermined interfaces are also declared in the corresponding docstrings.

    Nesting, branches, and suffixes are defined by passing additional phrase derivatives to a instace.

Parsing
=======

The top-level object ``RootPhrase`` provides the entry points for the parsing process.
The result will be a ``RootTokenBranch``.

Visualisation
=============

The visualization module provides some support for debugging.
All necessary packages can be installed separately.

.. code-block::
    console

    python3 -m pip install syntax-parser-prototype[visualisation] --upgrade


Overview
--------


.. code-block::
    python

    visualisation.start_structure_graph_app(root)

.. image:: https://raw.githubusercontent.com/srccircumflex/syntax-parser-prototype/master/docs/phrase-graph-app.png
    :align: center


.. code-block::
    python

    visualisation.html_on_server(result)


.. image:: https://raw.githubusercontent.com/srccircumflex/syntax-parser-prototype/master/docs/html-app.png
    :align: center


.. code-block::
    python

    print(visualisation.pretty_xml_result(result))

.. code-block::
    xml

    <?xml version="1.0" ?>
    <RB phrase="#root">
        <RN coord="0:0:0">''</RN>
        <B phrase="consoleline">
            <N coord="0:0:3">'&gt;&gt;&gt;'</N>
            <T coord="0:3:4">' '</T>
            <B phrase="function">
                <N coord="0:4:16">'prettyprint('</N>
                <B phrase="string">
                    <N coord="0:16:17">"'"</N>
                    <T coord="0:17:66">'( (a * b / (c + a)) * (b / (c – a) * b) / c ) + a'</T>
                    <N coord="0:66:67">"'"</N>
                </B>
                <N coord="0:67:68">')'</N>
            </B>
            <N coord="0:68:68">''</N>
        </B>
        <RT coord="0:68:69">'\n'</RT>
        <B phrase="bracket">
            <N coord="1:0:1">'('</N>
            <T coord="1:1:2">'\n'</T>
            <T coord="2:0:3">'   '</T>
            <B phrase="bracket">
                <N coord="2:3:4">'('</N>
                <T coord="2:4:5">'\n'</T>
                <T coord="3:0:7">'       '</T>
                <T coord="3:7:8">'a'</T>
                <T coord="3:8:9">' '</T>
                <T coord="3:9:10">'*'</T>
                <T coord="3:10:11">' '</T>
                <T coord="3:11:12">'b'</T>
                <T coord="3:12:13">' '</T>
                <T coord="3:13:14">'/'</T>
                <T coord="3:14:15">' '</T>
                <B phrase="bracket">
                    <N coord="3:15:16">'('</N>
                    <T coord="3:16:17">'c'</T>
                    <T coord="3:17:18">' '</T>
                    <T coord="3:18:19">'+'</T>
                    <T coord="3:19:20">' '</T>
                    <T coord="3:20:21">'a'</T>
                    <N coord="3:21:22">')'</N>
                </B>
                <T coord="3:22:23">'\n'</T>
                <T coord="4:0:3">'   '</T>
                <N coord="4:3:4">')'</N>
            </B>
            <T coord="4:4:5">' '</T>
            <T coord="4:5:6">'*'</T>
            <T coord="4:6:7">' '</T>
            <B phrase="bracket">
                <N coord="4:7:8">'('</N>
                <T coord="4:8:9">'\n'</T>
                <T coord="5:0:7">'       '</T>
                <T coord="5:7:8">'b'</T>
                <T coord="5:8:9">' '</T>
                <T coord="5:9:10">'/'</T>
                <T coord="5:10:11">' '</T>
                <B phrase="bracket">
                    <N coord="5:11:12">'('</N>
                    <T coord="5:12:13">'c'</T>
                    <T coord="5:13:16">' – '</T>
                    <T coord="5:16:17">'a'</T>
                    <N coord="5:17:18">')'</N>
                </B>
                <T coord="5:18:19">' '</T>
                <T coord="5:19:20">'*'</T>
                <T coord="5:20:21">' '</T>
                <T coord="5:21:22">'b'</T>
                <T coord="5:22:23">'\n'</T>
                <T coord="6:0:3">'   '</T>
                <N coord="6:3:4">')'</N>
            </B>
            <T coord="6:4:5">' '</T>
            <T coord="6:5:6">'/'</T>
            <T coord="6:6:7">' '</T>
            <T coord="6:7:8">'c'</T>
            <T coord="6:8:10">' \n'</T>
            <N coord="7:0:1">')'</N>
        </B>
        <RT coord="7:1:2">' '</RT>
        <T coord="7:2:3">'+'</T>
        <RT coord="7:3:4">' '</RT>
        <T coord="7:4:5">'a'</T>
        <RT coord="7:5:6">'\n'</RT>
        <RT coord="8:0:1">'\n'</RT>
        <B phrase="consoleline">
            <N coord="9:0:3">'&gt;&gt;&gt;'</N>
            <T coord="9:3:4">' '</T>
            <B phrase="function">
                <N coord="9:4:8">'int('</N>
                <B phrase="string">
                    <N coord="9:8:9">'"'</N>
                    <T coord="9:9:11">'42'</T>
                    <N coord="9:11:12">'"'</N>
                    <B phrase="angular brackets">
                        <N coord="9:12:13">'['</N>
                        <T coord="9:13:16">'1:3'</T>
                        <N coord="9:16:17">']'</N>
                    </B>
                </B>
                <T coord="9:17:18">' '</T>
                <T coord="9:18:19">'+'</T>
                <T coord="9:19:20">' '</T>
                <B phrase="string">
                    <N coord="9:20:21">'"'</N>
                    <T coord="9:21:22">'3'</T>
                    <N coord="9:22:23">'"'</N>
                </B>
                <N coord="9:23:24">')'</N>
            </B>
            <T coord="9:24:25">' '</T>
            <T coord="9:25:26">'+'</T>
            <T coord="9:26:27">' '</T>
            <T coord="9:27:29">'19'</T>
            <N coord="9:29:29">''</N>
        </B>
        <RT coord="9:29:30">'\n'</RT>
        <T coord="10:0:2">'42'</T>
        <RT coord="10:2:3">'\n'</RT>
        <RN coord="10:3:3">''</RN>
    </RB>
