"""PostToolUse hook: check the file an Edit or Write just changed, and hand any problem back.

- `.py`: `ruff check` on that file. Never `ruff format` -- the Makefile keeps a wholesale reformat
  out of every gate, and a hook that reformats on save would be one.
- `.md`: paragraphs, bullets and quotes must not be hard-wrapped (docs/naming_convention.md,
  "Markdown in this repository").

Exit 2 shows stderr to the agent, which then fixes the file. Files outside the repository are left
alone. Standard library only: this runs under whatever `python3` is on PATH, outside the venv.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
QUOTE = re.compile(r"^\s*(>\s?)+")
ITEM = re.compile(r"^([-*+]|\d+[.)])\s+\S")
# A line that is a block of its own and carries no paragraph text: heading, table row, rule or
# setext underline, HTML, image or badge, footnote or link definition, or a Jinja tag in a dbt
# docs file. Nothing that follows one continues it.
BLOCK = re.compile(r"^(#|\||[-*_=]{3,}\s*$|<|!\[|\[!\[|\{[%#{]|\[\^?[^\]]*\]:)")
INDENTED_CODE = re.compile(r"^( {4}|\t)")
# A Markdoc or Jinja tag left open on its line, as a report page writes a component: its attributes
# follow one per line until the line that closes it with `%}`.
OPEN_TAG = re.compile(r"^\{%(?!.*%\})")


def _front_matter_end(lines: list[str]) -> int:
    """Index of the first line after YAML front matter, as a skill or an agent file opens with."""
    if lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                return i + 1
    return 0


def wrapped_lines(text: str) -> list[int]:
    """1-based numbers of lines that continue the paragraph, bullet or quote above them."""
    lines = text.splitlines()
    found: list[int] = []
    fence = ""  # the marker that opened the fence we are in, or "" outside one
    in_comment = in_code = in_tag = False
    # Whether the line above holds paragraph or list-item text that a text line would continue.
    carries_text = False
    start = _front_matter_end(lines)
    for number, line in enumerate(lines[start:], start=start + 1):
        opener = FENCE.match(line)
        if fence:
            # Only the opening character, at least as long, closes it: ``` inside ```` is content.
            if opener and opener.group(1)[0] == fence[0] and len(opener.group(1)) >= len(fence):
                fence = ""
            carries_text = False
            continue
        if opener:
            fence = opener.group(1)
            carries_text = False
            continue
        if in_tag or OPEN_TAG.match(line.lstrip()):
            in_tag = "%}" not in line
            carries_text = False
            continue
        if in_comment or line.lstrip().startswith("<!--"):
            in_comment = "-->" not in line
            carries_text = False
            continue
        content = QUOTE.sub("", line, count=1).strip()
        if not content:
            carries_text = in_code = False
            continue
        # An indented line after a blank one opens indented code; it runs until the next blank.
        if in_code or (INDENTED_CODE.match(line) and not carries_text and number > start + 1
                       and not lines[number - 2].strip()):
            in_code = True
            continue
        if BLOCK.match(content):
            carries_text = False
            continue
        if not ITEM.match(content) and carries_text:
            found.append(number)
        # A trailing backslash or two spaces is a deliberate line break, not a wrap.
        carries_text = not line.endswith(("\\", "  "))
    return found


def check_markdown(path: Path) -> str | None:
    found = wrapped_lines(path.read_text(encoding="utf-8"))
    if not found:
        return None
    shown = ", ".join(str(n) for n in found[:10])
    return (
        f"{path}: prose is hard-wrapped at line(s) {shown}. One paragraph or bullet is one line "
        "in this repository (docs/naming_convention.md); join each with the line above it."
    )


def check_python(path: Path, root: Path) -> str | None:
    if shutil.which("uv") is None:
        return None
    result = subprocess.run(
        ["uv", "run", "--no-sync", "ruff", "check", "--quiet", str(path)],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode == 0:
        return None
    return (result.stdout + result.stderr).strip() or f"ruff check failed on {path}"


def main() -> int:
    payload = json.load(sys.stdin)
    file_path = payload.get("tool_input", {}).get("file_path")
    if not file_path:
        return 0
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or Path.cwd()).resolve()
    path = Path(file_path).resolve()
    if not path.is_file() or not path.is_relative_to(root):
        return 0
    if path.suffix == ".md":
        problem = check_markdown(path)
    elif path.suffix == ".py":
        problem = check_python(path, root)
    else:
        problem = None
    if problem is None:
        return 0
    print(problem, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
