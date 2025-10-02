import sys

import dash

from ..syntax_parser_prototype import *


def pretty_xml_result(branch: NodeToken | EOFToken) -> str:
    import xml.dom.minidom
    return xml.dom.minidom.parseString(repr(branch)).toprettyxml()


class _html_server:
    main_css = """\
    span {color: black; font-weight: normal;}
    """

    token_css = {
        NodeToken: 'color: blue; font-weight: bold;',
        DefaultToken: 'color: red',
        Token: '',
    }

    clicked_timeout = 0.2
    clicked = list()

    def __call__(
            self,
            branch: NodeToken | EOFToken,
            at_console: bool = (
                    type(__builtins__) is dict  # pycharm
                    or sys.stdout.isatty()  # terminal
                    or hasattr(sys, 'ps1')  # terminal
            ),
    ):
        from dash import Dash, html
        from threading import Thread
        from time import perf_counter

        _style = ('<style>' + self.main_css + str().join(f'.{t.id} {{{c}}}' for t, c in self.token_css.items()) + '</style>')

        app = Dash(__name__)

        root = html.Pre(children=[])
        trace = [root]

        if at_console:
            t = perf_counter()

            def __cb(token):
                @app.callback(
                    dash.Input(s, "n_clicks"),
                    prevent_initial_call=True,
                )
                def cb(_, token=token):
                    nonlocal t
                    _t = perf_counter()
                    if _t - t > self.clicked_timeout:
                        self.clicked.clear()
                    self.clicked.append(token)
                    t = _t

            run = Thread(target=app.run, kwargs=dict(debug=True, use_reloader=False), daemon=True).start

        else:

            def __cb(token):
                ...

            run = lambda: app.run(debug=True)

        for token in branch.gen_branch():
            classes = " ".join(i.id for i in reversed(type(token).mro()[:-1]))
            if isinstance(token, NodeToken):
                s = html.Span(className=str(token.phrase.id) + " " + classes, children=[token.content])
                trace[-1].children.append(s)
                trace.append(s)
                __cb(token)
            elif isinstance(token, EndToken):
                trace[-1].children.append(token.content)
                trace.pop()
            else:
                s = html.Span(className=classes, children=[token.content])
                trace[-1].children.append(s)
                __cb(token)

        app.layout = html.Div(children=[root])
        app.index_string = f'''
        <!DOCTYPE html>
        <html>
            <head>
                {_style}
            </head>
            <body>
                {{%app_entry%}}
                <footer>
                    {{%config%}}
                    {{%scripts%}}
                    {{%renderer%}}
                </footer>
            </body>
        </html>
        '''
        run()


html_server = _html_server()


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
