#!/usr/bin/env python3
"""Render a Markdown document to PDF.

Local authoring tool, not part of the deployed app. Exists because the repo's
long-form docs (DOCUMENTATION.md, LLM_ENGINEERING.md) are written in Markdown
so they stay diffable and render on GitHub, but are *read* as PDFs.

    python tools/md2pdf.py LLM_ENGINEERING.md
    python tools/md2pdf.py DOCUMENTATION.md -o docs/manual.pdf

How it works, and why this way:

  Markdown -> HTML   python-markdown. Pure Python, no Node toolchain.
  HTML     -> PDF    headless Edge/Chrome, already on every Windows machine.

That second step is the whole reason there is no WeasyPrint/wkhtmltopdf
dependency here: a browser is the only renderer on hand that runs mermaid,
and mermaid is the diagram format the rest of the repo's docs already use.

Mermaid is fetched once into ~/.cache/md2pdf/ and inlined into the HTML, so
every run after the first is fully offline and the 3.5MB blob never lands in
the repo.

Deliberately not implemented: page numbers. Chrome's print pipeline supports
neither CSS `@page` counters nor a custom footer template via the command
line, and its built-in footer drags the `file://` URL along with it. The
generated table of contents is hyperlinked instead, which navigates better
than page numbers do in a PDF reader.
"""

import argparse
import html
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

try:
    import markdown
except ImportError:
    sys.exit("Missing dependency. Run: pip install markdown pygments")

MERMAID_URL = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"
MERMAID_CACHE = Path.home() / ".cache" / "md2pdf" / "mermaid.min.js"

# Both are checked; whichever exists first is used. Edge ships with Windows,
# so the fallback almost never fires.
BROWSERS = [
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
]

# Mermaid wants <pre class="mermaid">, but python-markdown's fenced_code emits
# <pre><code class="language-mermaid"> and HTML-escapes the body. Rather than
# unpick that afterwards, the blocks are lifted out before conversion and put
# back after, so Markdown never sees them at all.
MERMAID_FENCE = re.compile(r"^```mermaid\n(.*?)^```$", re.MULTILINE | re.DOTALL)

CSS = """
@page { size: A4; margin: 18mm 16mm 18mm 16mm; }

:root {
  --ink: #1a1a1a; --muted: #5b5b5b; --rule: #d8d8d8;
  --code-bg: #f6f6f4; --accent: #8b2f2f;
}

body {
  font-family: "Charter", "Georgia", "Cambria", serif;
  font-size: 10.5pt; line-height: 1.55; color: var(--ink);
  max-width: 100%; margin: 0; hyphens: auto;
}

/* Every H1 is a chapter. Chapters start on a fresh sheet. */
h1 { break-before: page; font-size: 21pt; line-height: 1.2; margin: 0 0 1.2em;
     padding-bottom: .35em; border-bottom: 2.5px solid var(--accent); font-weight: 700; }
h1:first-of-type { break-before: avoid; }
h2 { font-size: 15pt; margin: 1.8em 0 .6em; padding-bottom: .2em;
     border-bottom: 1px solid var(--rule); font-weight: 700; }
h3 { font-size: 12.5pt; margin: 1.4em 0 .45em; font-weight: 700; }
h4 { font-size: 11pt; margin: 1.2em 0 .35em; font-weight: 700; color: var(--muted); }

/* A heading stranded at the foot of a page is the most common ugly artefact
   in a long printed document. */
h1, h2, h3, h4 { break-after: avoid; break-inside: avoid; }
p, li { orphans: 3; widows: 3; }

code, kbd { font-family: "Cascadia Mono", "Consolas", monospace; font-size: .86em;
            background: var(--code-bg); padding: .1em .3em; border-radius: 3px; }
pre { background: var(--code-bg); border: 1px solid var(--rule); border-left: 3px solid var(--accent);
      padding: .7em .9em; border-radius: 4px; overflow-x: auto; break-inside: avoid;
      font-size: 8.8pt; line-height: 1.42; white-space: pre-wrap; word-wrap: break-word; }
pre code { background: none; padding: 0; font-size: 1em; }

table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 9.3pt;
        break-inside: avoid; }
th, td { border: 1px solid var(--rule); padding: .42em .6em; text-align: left;
         vertical-align: top; }
th { background: #efefec; font-weight: 700; }
tr:nth-child(even) td { background: #fafaf8; }

blockquote { margin: 1em 0; padding: .55em 1em; border-left: 3px solid var(--accent);
             background: #faf7f7; color: var(--muted); break-inside: avoid; }
blockquote p { margin: .3em 0; }

hr { border: 0; border-top: 1px solid var(--rule); margin: 2em 0; }
a { color: var(--accent); text-decoration: none; }
img, svg { max-width: 100%; }

/* Mermaid renders into the <pre>; keep a diagram whole on one page. */
pre.mermaid { background: none; border: none; text-align: center;
              break-inside: avoid; padding: .8em 0; }

/* python-markdown's [TOC] output. */
.toc { break-after: page; font-size: 10pt; }
.toc ul { list-style: none; padding-left: 1.1em; margin: .2em 0; }
.toc > ul { padding-left: 0; }
.toc a { color: var(--ink); }
.toc li { margin: .12em 0; }
"""

# mermaid.initialize is deliberately startOnLoad:true with no await: the
# --virtual-time-budget below is what actually guarantees rendering finished
# before the PDF is captured.
HTML_SHELL = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{title}</title>
<style>{css}</style></head>
<body>
{body}
<script>{mermaid}</script>
<script>mermaid.initialize({{startOnLoad:true, theme:'neutral',
  themeVariables:{{fontFamily:'Georgia, serif', fontSize:'14px'}},
  flowchart:{{useMaxWidth:true}}}});</script>
</body></html>
"""


def mermaid_js() -> str:
    """The library, from cache, fetching once if absent.

    A failed fetch is not fatal: the document still renders, and any mermaid
    block degrades to the monospaced source text rather than to nothing.
    """
    if MERMAID_CACHE.exists():
        return MERMAID_CACHE.read_text(encoding="utf-8")
    try:
        print(f"[md2pdf] fetching mermaid -> {MERMAID_CACHE}")
        MERMAID_CACHE.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(MERMAID_URL, timeout=60) as response:
            js = response.read().decode("utf-8")
        MERMAID_CACHE.write_text(js, encoding="utf-8")
        return js
    except Exception as error:
        print(f"[md2pdf] WARNING: no mermaid ({error}); diagrams stay as source text")
        return ""


def find_browser() -> Path:
    for path in BROWSERS:
        if path.exists():
            return path
    sys.exit("No Edge or Chrome found; install one or edit BROWSERS in this script.")


def to_html(md_text: str, title: str) -> str:
    diagrams: list[str] = []

    def stash(match: re.Match) -> str:
        diagrams.append(match.group(1))
        return f"\n<!--MERMAID{len(diagrams) - 1}-->\n"

    md_text = MERMAID_FENCE.sub(stash, md_text)

    body = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "toc", "attr_list", "sane_lists", "admonition"],
        extension_configs={"toc": {"title": "Contents", "toc_depth": "1-3"}},
    )

    for i, source in enumerate(diagrams):
        body = body.replace(
            f"<!--MERMAID{i}-->", f'<pre class="mermaid">{html.escape(source)}</pre>'
        )

    return HTML_SHELL.format(title=html.escape(title), css=CSS, body=body, mermaid=mermaid_js())


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a Markdown file to PDF.")
    parser.add_argument("source", type=Path, help="the .md file")
    parser.add_argument("-o", "--output", type=Path, help="the .pdf (default: alongside source)")
    parser.add_argument("--keep-html", action="store_true", help="leave the intermediate HTML")
    args = parser.parse_args()

    if not args.source.is_file():
        sys.exit(f"No such file: {args.source}")

    output = (args.output or args.source.with_suffix(".pdf")).resolve()
    md_text = args.source.read_text(encoding="utf-8")
    page = to_html(md_text, args.source.stem.replace("_", " ").title())

    # Written next to the source so relative image paths in the Markdown keep
    # resolving; the browser reads it over file://.
    html_path = args.source.resolve().with_suffix(".md2pdf.html")
    html_path.write_text(page, encoding="utf-8")

    print(f"[md2pdf] {len(md_text):,} chars -> {len(page):,} chars HTML -> rendering...")
    result = subprocess.run(
        [
            str(find_browser()),
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            "--run-all-compositor-stages-before-draw",
            # Mermaid renders asynchronously after load. Virtual time lets the
            # browser fast-forward its clock, so this is a ceiling, not a sleep.
            "--virtual-time-budget=30000",
            f"--print-to-pdf={output}",
            html_path.as_uri(),
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )

    # The browser process can still hold the file for a moment after the PDF is
    # written, which on Windows is a hard lock rather than a no-op. Cleanup is
    # not worth failing a 3-minute render over.
    if not args.keep_html:
        try:
            html_path.unlink(missing_ok=True)
        except OSError:
            print(f"[md2pdf] note: could not remove {html_path.name}")

    if not output.exists():
        sys.exit(f"Render failed (exit {result.returncode}):\n{result.stderr[-2000:]}")
    print(f"[md2pdf] wrote {output} ({output.stat().st_size / 1_048_576:.1f} MB)")


if __name__ == "__main__":
    main()
