from syntax_parser_prototype import RootPhrase, RootBranch, RootToken, RootNodeToken, Branch, Token, NodeToken


def pretty_xml_result(branch: Branch) -> str:
    import xml.dom.minidom
    return xml.dom.minidom.parseString(repr(branch)).toprettyxml()


def html_on_server(branch: Branch):
    import dash_dangerously_set_inner_html
    from dash import Dash, html

    _html = f"""\
    <style>
    .{RootNodeToken.xml_label} {{color: red;}}
    .{NodeToken.xml_label} {{color: blue;}}
    .{RootToken.xml_label} {{color: orange;}}
    .{Token.xml_label} {{color: black;}}
    </style>
    """

    _html += "<pre>"
    for token in branch.gen_inner():
        data_id = ""
        if isinstance(token, RootNodeToken):
            data_id = token.branch.phrase.id
        elif isinstance(token, NodeToken):
            data_id = token.branch.phrase.id
        _html += f"<span data-id={data_id} class={token.xml_label!r}>{token.content}</span>"
    _html += "</pre>"

    app = Dash(__name__)

    app.layout = html.Div([
        dash_dangerously_set_inner_html.DangerouslySetInnerHTML(_html),
    ])
    app.run(debug=True)


def start_structure_graph_app(root: RootPhrase):
    from dash import Dash, html
    import dash_cytoscape as cyto

    touched = {root}
    elements = [{'data': {'id': root.id, 'label': root.id}, "classes": "red"}]

    def f(phrase):
        if phrase not in touched:
            touched.add(phrase)
            p_id = f'{phrase.id}'
            elements.append({'data': {'id': p_id, 'label': p_id}})
            for sub_phrase in phrase.__sub_phrases__:
                sp_id = f'{sub_phrase.id}'
                elements.append({'data': {'id': f"{p_id}\u2007{sp_id}", 'source': p_id, 'target': sp_id}, "classes": "dir"})
                f(sub_phrase)

    for p in root.__sub_phrases__:
        sp_id = f'{p.id}'
        elements.append({'data': {"id": f"{root.id}\u2007{sp_id}", 'source': root.id, 'target': sp_id}, "classes": "dir"})
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
                    'selector': '.dir',
                    'style': {
                        'target-arrow-shape': 'triangle',
                        'target-arrow-color': 'blue',
                    }
                },
            ]
        )
    ], style={"position": "absolute", "top": 0, "bottom": 0, "left": 0, "right": 0})
    app.run(debug=True)
