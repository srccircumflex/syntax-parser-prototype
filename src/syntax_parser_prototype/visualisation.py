from ..syntax_parser_prototype import *


def pretty_xml_result(branch: NodeToken | EOFToken) -> str:
    import xml.dom.minidom
    return xml.dom.minidom.parseString(repr(branch)).toprettyxml()


class html_on_server:
    main_css = """\
    span {color: black; font-weight: normal;}
    """

    token_css = {
        NodeToken: 'color: blue; font-weight: bold;',
        DefaultToken: 'color: red',
        Token: '',
    }

    def __init__(
            self,
            branch: NodeToken | EOFToken,
            linear_layout: bool = False,
    ):
        import dash_dangerously_set_inner_html
        from dash import Dash, html

        _html = ('<style>' + self.main_css + str().join(f'.{t.xml_label} {{{c}}}' for t, c in self.token_css.items()) + '</style>')

        if linear_layout:
            _html += "<pre>"
            for token in branch.gen_branch():
                _id = ""
                if isinstance(token, NodeToken):
                    _id = f" id={str(token.phrase.id)!r}"
                _html += f"<span{_id} class={token.xml_label!r}>{token.content}</span>"
            _html += "</pre>"

        else:
            _html += "<pre>"
            for token in branch.gen_branch():
                if isinstance(token, NodeToken):
                    _html += f"<span id={str(token.phrase.id)!r} class={token.xml_label!r}>{token.content}"
                elif isinstance(token, EndToken):
                    _html += f"{token.content}</span>"
                else:
                    _html += f"<span class={token.xml_label!r}>{token.content}</span>"
            _html += "</pre>"

        app = Dash(__name__)

        app.layout = html.Div([
            dash_dangerously_set_inner_html.DangerouslySetInnerHTML(  # type: ignore
                _html
            ),
        ])
        app.run(debug=True)


def start_structure_graph_app(root: MainPhrase):
    from dash import Dash, html
    import dash_cytoscape as cyto

    touched = {root}
    elements = [{'data': {'id': str(root.id), 'label': str(root.id)}, "classes": "red"}]

    def f(phrase):
        if phrase not in touched:
            touched.add(phrase)
            p_id = f'{phrase.id}'
            elements.append({'data': {'id': p_id, 'label': p_id}})
            for sub_phrase in phrase.__sub_phrases__:
                sp_id = f'{sub_phrase.id}'
                elements.append({'data': {'id': f"{p_id}\u2007{sp_id}", 'source': p_id, 'target': sp_id}, "classes": "sub"})
                f(sub_phrase)
            for suffix_phrase in phrase.__suffix_phrases__:
                sp_id = f'{suffix_phrase.id}'
                elements.append({'data': {'id': f"{p_id}\u2007{sp_id}", 'source': p_id, 'target': sp_id}, "classes": "suffix"})
                f(suffix_phrase)

    for p in root.__sub_phrases__:
        sp_id = f'{p.id}'
        elements.append({'data': {"id": f"{root.id}\u2007{sp_id}", 'source': root.id, 'target': sp_id}, "classes": "sub"})
        f(p)

    app = Dash(__name__)

    app.layout = html.Div([
        cyto.Cytoscape(
            layout={'name': 'circle'},
            style={'width': '100%', 'height': '100%'},
            elements=elements,
            stylesheet=[
                {
                    'selector': 'node',
                    'style': {
                        'content': 'data(label)'
                    }
                },
                {
                    'selector': 'edge',
                    'style': {
                        # The default curve style does not work with certain arrows
                        'curve-style': 'bezier'
                    }
                },
                {
                    'selector': '.red',
                    'style': {
                        'background-color': 'red',
                    }
                },
                {
                    'selector': '.sub',
                    'style': {
                        'target-arrow-shape': 'triangle',
                        'target-arrow-color': 'blue',
                    }
                },
                {
                    'selector': '.suffix',
                    'style': {
                        'target-arrow-shape': 'triangle',
                        'target-arrow-color': 'green',
                    }
                },
            ]
        )
    ], style={"position": "absolute", "top": 0, "bottom": 0, "left": 0, "right": 0})
    app.run(debug=True)
