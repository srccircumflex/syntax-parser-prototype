from __future__ import annotations

from types import ModuleType


def run_parser(
        m_config: ModuleType,
        m_template: ModuleType,
):
    with open(m_template.__file__) as f:
        content = f.read()
        main = m_config.main()
        result = main.parse_string(content)

    result_content = str().join(i.content for i in result.tokenReader.branch)
    if result_content != content:
        out = __file__ + ".missmatch.py"
        import warnings
        warnings.warn(f"content mismatch -> writing to {out}")
        with open(out, "w") as f:
            f.write(result_content)

    return main, content, result, result_content


if __name__ == "__main__":
    from demos.pysyntax import config
    from demos.pysyntax import template
    from src.syntax_parser_prototype import debug
    debug.html_server.main_css += "pre { font-family: monospace; background-color: #2f2c2c;} span { color: #c8c8c8;}"

    main, content, result, result_content = run_parser(config, template)

    # print(root.__repr__())
    # print(result.__repr__())
    # print(debug.pretty_xml(result))
    debug.html_server(result)
    # debug.structure_graph_app(main)
