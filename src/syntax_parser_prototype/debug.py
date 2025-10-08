from __future__ import annotations

from functools import lru_cache
from typing import Literal, Type, Callable

from .main import phrase, streams, tokens
from .features import readers


__all__ = ("__repr__", "pretty_xml", "html_server", "structure_graph_app")


class _Repr(
    dict[
        Type[tokens.Token | streams.Stream | streams.TokenizeStream | phrase.Phrase | readers.TokenReader],
        dict[
            Type[tokens.Token | streams.Stream | streams.TokenizeStream | phrase.Phrase] | type,
            Callable[[tokens.Token | streams.Stream | streams.TokenizeStream | phrase.Phrase], str]
        ]
    ]
):
    """Dynamic, type-controlled registry and dispatcher system for repr representations
    of parser objects (Token, NodeToken, EndToken, Stream, TokenizeStream, Phrase).

    It overrides and controls at runtime which function is used to represent an object—based
    on its type and MRO—and attaches itself to the classes as a descriptor so that obj.__repr__()
    automatically calls the appropriate formatting function.
    """

    def __init__(self):
        super().__init__()

        def __set_root__(t, f):
            super(_Repr, self).__setitem__(t, {t: f})
            t.__repr__ = self

        __set_root__(tokens.Token, self.Token__repr__)
        __set_root__(streams.Stream, self.Sream__repr__)
        __set_root__(streams.TokenizeStream, self.TokenizeStream__repr__)
        __set_root__(phrase.Phrase, self.Phrase__repr__)
        __set_root__(readers.TokenReader, self.TokenReader__repr__)
        with self:
            self[tokens.NodeToken] = self.NodeToken__repr__simple

    def Token__repr__(self, t: tokens.Token):
        return f'<{t.id} coord="{t.row_no} {t.column_start}:{t.column_end}">{t.content}</{t.id}>'

    def NodeToken__repr__recursive(self, n: tokens.NodeToken):
        return f'<{n.id} phrase="{str(n.phrase.id)}" coord="{n.row_no} {n.column_start}:{n.column_end}">{n.content}{str().join(repr(i) for i in n.inner)}{repr(n.end)}</{n.id}>'

    def NodeToken__repr__simple(self, n: tokens.NodeToken):
        return f'<{n.id} phrase="{str(n.phrase.id)}" coord="{n.row_no} {n.column_start}:{n.column_end}">{n.content}</{n.id}>'

    def Sream__repr__(self, s: streams.Stream):
        return f'<{s.__class__.__name__} row_no={s.row_no} viewpoint={s.viewpoint}>'

    def TokenizeStream__repr__(self, ts: streams.TokenizeStream):
        return f'<{ts.__class__.__name__} {ts.designated!r} row_no={ts.__stream__.row_no} viewpoint={ts.__stream__.viewpoint}>'

    def Phrase__repr__(self, p: phrase.Phrase):
        return f'<{p.__class__.__name__} {str(p.id)}>'

    def TokenReader__repr__(self, tr: readers.TokenReader):
        return f'<{tr.__class__.__name__}(reverse={tr.__reverse__}) @ {tr.__token__!r}>'

    def __hash__(self):
        return id(self)

    @lru_cache
    def _get_root(self, t: Type[tokens.Token | streams.Stream | streams.TokenizeStream | phrase.Phrase]):
        for k in self:
            if issubclass(t, k):
                return super().__getitem__(k)
        raise KeyError(t)

    @lru_cache
    def _get_func(self, t: Type[tokens.Token | streams.Stream | streams.TokenizeStream | phrase.Phrase]) -> Callable[[tokens.Token | streams.Stream | streams.TokenizeStream | phrase.Phrase], str]:
        cache = self._get_root(t)
        for c in (t.mro()  # type: ignore (parameter self unfilled)
                  [:-1]):  # exclude <object>
            if f := cache.get(c):
                return f
        return t.__repr__  # type: ignore (parameter self unfilled)

    def __getitem__(self, t: Type[tokens.Token | streams.Stream | streams.TokenizeStream | phrase.Phrase]) -> Callable[[tokens.Token | streams.Stream | streams.TokenizeStream | phrase.Phrase], str]:
        return self._get_func(t)

    def __get__(self, instance, owner):
        self.__instance__ = instance
        return self

    def __call__(self, o: tokens.Token | streams.Stream | streams.TokenizeStream | phrase.Phrase = None):
        if o is None:
            o = self.__instance__
        return self._get_func(type(o))(o)

    __incontext__: bool = False

    def __setitem__(self, t, f):
        if not self.__incontext__:
            raise RuntimeError("Apply your custom configuration within the context manager\n"
                               "e.g.:\n"
                               ">>> with debug.__repr__:\n"
                               "...     debug.__repr__[NodeToken] = debug.__repr__[Token]")
        cache = self._get_root(t)
        cache[t] = f
        t.__repr__ = self

    def __enter__(self):
        self.__incontext__ = True
        return self

    def cache_clear(self):
        self._get_func.cache_clear()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.__incontext__ = False
        self.cache_clear()


__repr__ = _Repr()
"""Dynamic, type-controlled registry and dispatcher system for repr functionalities
of parser objects (Token, NodeToken, EndToken, Stream, TokenizeStream, Phrase).
If a subtype is not defined, the inheritance hierarchy is searched.

ex.::

    >>> with debug.__repr__:
    ...     debug.__repr__[NodeToken] = lambda t: t.content
    ...     debug.__repr__[MyToken] = lambda t: 'my-' + debug.__repr__[Token](t)
"""


def pretty_xml(branch: tokens.NodeToken | tokens.EOF) -> str:
    """Converts the representation of a branch into a formatted,
    pretty-printed XML string for better readability.
    """
    _repr = __repr__[tokens.NodeToken]
    with __repr__:
        __repr__[tokens.NodeToken] = __repr__.NodeToken__repr__recursive
    try:
        string = repr(branch)
    finally:
        with __repr__:
            __repr__[tokens.NodeToken] = _repr
    import xml.dom.minidom
    return xml.dom.minidom.parseString(string).toprettyxml()


class _html_server:
    """This server is designed to render and display hierarchical branches provided as input
    tokens in a web application, applying customizable CSS styling and tracking user interaction
    with the rendered elements. The server can operate seamlessly in various terminal or non-terminal
    environments and employs callback functions to handle visual or user interaction updates.
    """

    main_css = """\
    span {color: black; font-weight: normal;}
    """

    token_css = {
        tokens.NodeToken: 'color: blue; font-weight: bold;',
        tokens.OToken: 'color: red',
        tokens.Token: '',
    }

    click_bubble_timeout = 0.2
    clicked = list()
    
    @staticmethod
    def at_console_default():
        import os
        import sys
        if hasattr(sys, 'ps1'):
            # python console
            return True
        elif os.environ.get('IPYTHONENABLE'):
            # pycharm
            try:
                import pydevd  # type: ignore
                if pydevd.get_global_debugger():
                    # debugger
                    return False
            except ImportError:
                pass
            return True
        else:
            return False

    def __call__(
            self,
            branch: tokens.NodeToken | tokens.EOF,
            at_console: bool = None,
    ):
        from dash import Dash, html, Input
        from threading import Thread
        from time import perf_counter

        _style = ('<style>' + self.main_css + str().join(f'.{t.id} {{{c}}}' for t, c in self.token_css.items()) + '</style>')

        app = Dash(__name__)

        root = html.Pre(children=[])
        trace: list[html.Pre | html.Span] = [root]

        if at_console if at_console is not None else self.at_console_default():
            t = perf_counter()

            def __cb(token):
                @app.callback(
                    Input(s, "n_clicks"),
                    prevent_initial_call=True,
                )
                def cb(_, token=token):
                    nonlocal t
                    _t = perf_counter()
                    if _t - t > self.click_bubble_timeout:
                        self.clicked.clear()
                    self.clicked.append(token)
                    t = _t

            run = Thread(target=app.run, kwargs=dict(debug=True, use_reloader=False), daemon=True).start

        else:

            def __cb(token):
                ...

            run = lambda: app.run(debug=True)

        for token in branch.tokenReader.branch:
            classes = " ".join(i.id for i in reversed(type(token).mro()[:-1]))  # -1: object
            if isinstance(token, tokens.NodeToken):
                s = html.Span(className=str(token.phrase.id) + " " + classes, children=[token.content])
                trace[-1].children.append(s)
                trace.append(s)
                __cb(token)
            elif isinstance(token, tokens.EndToken):
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


def structure_graph_app(
        root: phrase.Root,
        layout: Literal[
            "dagre",
            "preset",
            "random",
            "grid",
            "circle",
            "concentric",
            "breadthfirst",
            "cose",
            "cose-bilkent",
            "cola",
            # "euler", not supported because it creates an infinite loop
            "spread",
            "dagre",
            "klay",
        ] = "dagre",
        layout_params: dict = None,
):
    """
    Starts a Dash web application to visually represent a structural graph of phrases
    and their relationships. The graph uses Dash Cytoscape for rendering and provides
    different layout algorithms for user interaction.

    **WARNING: This feature uses the project dash_cytoscape, which is marked as failed and may not work as intended.**

    :param root: The root phrase from which the graph structure is generated.
    :type root: Root
    :param layout: The layout algorithm to be used for visualizing the graph.
        Supported options include "dagre", "preset", "random", "grid", "circle",
        "concentric", "breadthfirst", "cose", "cose-bilkent", "cola", "spread", and "klay"
        (https://dash.plotly.com/cytoscape/layout).
        The "euler" layout is not supported because it creates an infinite loop.
    :param layout_params: Optional parameters for customizing the specified layout.
    :type layout_params: dict, optional
    :return: None
    """
    if layout == "euler":
        raise ValueError("The 'euler' layout is not supported because it creates an infinite loop.")

    import dash_cytoscape as cyto
    import dash

    import warnings
    warnings.warn(f"This feature uses the project dash_cytoscape, "
                  f"which is marked as failed and may not work as intended.")

    if cyto.__version__ != "0.2.0":
        raise ValueError(f"dash_cytoscape version == 0.2.0 is required "
                         f"(version: {cyto.__version__})\n"
                         f">>> pip install dash_cytoscape==0.2.0")
    if dash.__version__[0] != "2":
        warnings.warn(f"dash of version > 2 may encounter a deprecated React method "
                      f"when used in combination with dash_cytoscape (version: {dash.__version__})")

    cyto.load_extra_layouts()

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

    app = dash.Dash(__name__)

    app.layout = dash.html.Div([
        cyto.Cytoscape(
            layout={'name': layout} | (layout_params or {}),
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
