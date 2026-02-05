from __future__ import annotations

import argparse
from pathlib import Path

import markdown


def render_markdown_to_html(md_text: str) -> str:
    return markdown.markdown(md_text, extensions=["extra", "toc", "tables"])


def build_html_document(title: str, body_html: str, css_href: str) -> str:
    # GitHub Markdown CSS + small wrapper to center content.
    #
    # Important: GitHub Markdown CSS respects `prefers-color-scheme`.
    # If the viewer is in dark mode, it may set light-colored text variables.
    # We force a light theme here to ensure high contrast on white paper-style backgrounds.
    return "\n".join(
        [
            "<!doctype html>",
            '<html style="color-scheme: light;">',
            "  <head>",
            '    <meta charset="utf-8" />',
            '    <meta name="viewport" content="width=device-width, initial-scale=1" />',
            f'    <link rel="stylesheet" href="{css_href}" />',
            "    <style>",
            "      body { margin: 0; background: #0b0f14; }",
            "      .markdown-body {",
            "        /* Force GitHub light theme variables (prevents washed-out text in dark-mode browsers) */",
            "        --fgColor-default: #1f2328;",
            "        --fgColor-muted: #656d76;",
            "        --fgColor-accent: #0969da;",
            "        --bgColor-default: #ffffff;",
            "        --bgColor-muted: #f6f8fa;",
            "        --borderColor-default: #d0d7de;",
            "        color: var(--fgColor-default);",
            "        box-sizing: border-box;",
            "        min-width: 200px;",
            "        max-width: 980px;",
            "        margin: 0 auto;",
            "        padding: 45px;",
            "        background: #ffffff;",
            "      }",
            "      .markdown-body a { color: var(--fgColor-accent); }",
            "      .markdown-body hr { border-color: var(--borderColor-default); }",
            "      .markdown-body pre, .markdown-body code { background: var(--bgColor-muted); }",
            "      @media (max-width: 767px) {",
            "        .markdown-body { padding: 15px; }",
            "      }",
            "    </style>",
            f"    <title>{title}</title>",
            "  </head>",
            "  <body>",
            '    <article class="markdown-body">',
            body_html,
            "    </article>",
            "  </body>",
            "</html>",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert Markdown to a styled standalone HTML file.")
    parser.add_argument("--input", required=True, help="Path to input .md file")
    parser.add_argument("--output", required=True, help="Path to output .html file")
    parser.add_argument(
        "--css",
        default="https://cdn.jsdelivr.net/npm/github-markdown-css@5/github-markdown.min.css",
        help="CSS href to use for styling (default: GitHub Markdown CSS from CDN)",
    )
    args = parser.parse_args()

    inp = Path(args.input)
    out = Path(args.output)

    md_text = inp.read_text(encoding="utf-8")
    body = render_markdown_to_html(md_text)
    html = build_html_document(title=inp.stem, body_html=body, css_href=args.css)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

