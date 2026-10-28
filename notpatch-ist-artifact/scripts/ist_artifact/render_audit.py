#!/usr/bin/env python3
"""Render AUDIT.md from AUDIT_TEMPLATE.md and the generated LaTeX tables.

Standard library only. Each {{table:<name>}} placeholder in the template is replaced by the
tables of paper/generated/<name>.tex, converted to GitHub Markdown. Paths are relative to
--root, which defaults to the package root:

    python3 scripts/ist_artifact/render_audit.py
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLACEHOLDER = re.compile(r"\{\{table:([A-Za-z0-9_]+)\}\}")
RULES = re.compile(r"\\(hline|toprule|midrule|bottomrule)\b")
MATH_SYMBOLS = {r"\kappa": "κ", r"\geq": "≥", r"\leq": "≤", r"\times": "×"}
PLAIN = [("\\_", "_"), ("\\%", "%"), ("\\&", "&"), ("{,}", ","), ("\\quad", "&emsp;"),
         ("---", "—"), ("--", "–"), ("``", "“"), ("''", "”"), ("~", " "), ("|", "\\|")]


def braced(text: str, start: int) -> tuple[str, int]:
    # Content of the balanced {...} group opening at text[start], and the index after it.
    if text[start] != "{":
        raise ValueError(f"expected '{{' at {start}: {text[start:start + 30]!r}")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{" and text[i - 1] != "\\":
            depth += 1
        elif text[i] == "}" and text[i - 1] != "\\":
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i + 1
    raise ValueError(f"unbalanced braces: {text[start:start + 30]!r}")


def plain(text: str) -> str:
    for old, new in PLAIN:
        text = text.replace(old, new)
    return text


def math(text: str) -> str:
    text = re.sub(r"\^\{?([A-Za-z0-9]+)\}?", r"<sup>\1</sup>", text)
    for old, new in MATH_SYMBOLS.items():
        text = text.replace(old, new)
    return text.replace("-", "−").replace("{,}", ",").replace(" ", "")


def inline(text: str) -> str:
    out, run, i = [], [], 0

    def flush() -> None:
        out.append(plain("".join(run)))
        run.clear()

    while i < len(text):
        command = re.match(r"\\(path|texttt|emph)\{", text[i:])
        if command:
            flush()
            arg, i = braced(text, i + len(command.group(0)) - 1)
            if command.group(1) == "emph":
                out.append("*" + inline(arg) + "*")
            else:
                out.append("`" + arg.replace("\\_", "_") + "`")
        elif text[i] == "$":
            flush()
            end = text.index("$", i + 1)
            out.append(math(text[i + 1:end]))
            i = end + 1
        else:
            run.append(text[i])
            i += 1
    flush()
    return re.sub(r"\s+", " ", "".join(out)).strip()


def cells(row: str) -> list[str]:
    span = re.match(r"\\multicolumn\{(\d+)\}", row)
    if span:
        _, after_spec = braced(row, span.end())
        text, _ = braced(row, after_spec)
        label = inline(text)
        return [label if label.startswith("*") else f"**{label}**"] + [""] * (int(span.group(1)) - 1)
    return [inline(cell) for cell in re.split(r"(?<!\\)&", row)]


def tabular_markdown(body: str) -> str:
    rows = []
    for raw in re.split(r"\\\\", body):
        raw = RULES.sub("", raw).strip()
        if raw:
            rows.append(cells(raw))
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    keep = [j for j in range(width) if any(r[j] for r in rows)]  # drop spacer columns
    rows, width = [[r[j] for j in keep] for r in rows], len(keep)
    lines = ["| " + " | ".join(rows[0]) + " |", "|" + " --- |" * width]
    lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(lines)


def tables_markdown(tex: str) -> str:
    tex = "\n".join(line for line in tex.splitlines() if not line.lstrip().startswith("%"))
    blocks = re.findall(r"\\begin\{table\*?\}(.*?)\\end\{table\*?\}", tex, re.S)
    if not blocks:
        raise ValueError("no table environment found")
    rendered = []
    for block in blocks:
        parts = []
        if "\\caption{" in block:
            caption, _ = braced(block, block.index("\\caption{") + len("\\caption"))
            parts.append(f"**Table: {inline(caption)}**")
        for match in re.finditer(r"\\begin\{tabular\}", block):
            _, start = braced(block, match.end())
            parts.append(tabular_markdown(block[start:block.index("\\end{tabular}", start)]))
        for note in re.findall(r"\\begin\{minipage\}\{[^}]*\}(.*?)\\end\{minipage\}", block, re.S):
            parts.append(inline(re.sub(r"\\footnotesize\b", "", note)))
        rendered.append("\n\n".join(parts))
    text = "\n\n".join(rendered)
    leftover = re.search(r"\\[A-Za-z]+", re.sub(r"`[^`]*`", "", text))
    if leftover:
        raise ValueError(f"unconverted LaTeX command {leftover.group(0)}")
    return text


def render(template: Path, generated: Path) -> str:
    def table(match: re.Match) -> str:
        return tables_markdown((generated / f"{match.group(1)}.tex").read_text(encoding="utf-8"))

    return PLACEHOLDER.sub(table, template.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=ROOT, help="package root (default: two levels above this script)")
    parser.add_argument("--template", default="scripts/ist_artifact/AUDIT_TEMPLATE.md", help="template, relative to --root")
    parser.add_argument("--generated", default="paper/generated", help="generated-table directory, relative to --root")
    parser.add_argument("--out", default="AUDIT.md", help="output file, relative to --root")
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        text = render(root / args.template, root / args.generated)
    except (OSError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    (root / args.out).write_text(text, encoding="utf-8")
    print(f"OK: wrote {root / args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
