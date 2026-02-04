#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape as xml_escape


DEFAULT_EXCLUDE_DIRS = {
    ".git",
    ".github",
    ".idea",
    ".vscode",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "coverage",
    ".next",
    ".nuxt",
    "out",
    "target",
}

DEFAULT_EXCLUDE_FILES = {
    "README.md",
    "README.MD",
    "LICENSE",
    "LICENSE.md",
    "LICENSE.txt",
    "COPYING",
    ".gitignore",
    ".gitattributes",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "poetry.lock",
    "Pipfile.lock",
    "Cargo.lock",
}

DEFAULT_EXCLUDE_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
    ".pdf",
    ".zip",
    ".gz",
    ".tar",
    ".tgz",
    ".7z",
    ".rar",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".eot",
    ".mp3",
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".wav",
    ".flac",
    ".db",
    ".sqlite",
    ".sqlite3",
}


def is_probably_binary(data: bytes) -> bool:
    if b"\x00" in data:
        return True
    if not data:
        return False
    sample = data[:4096]
    nontext = sum(1 for b in sample if b < 9 or (13 < b < 32))
    return (nontext / len(sample)) > 0.12


_WORD_CHARS = re.compile(r"[A-Za-z0-9_$]")


def _is_word_char(ch: str) -> bool:
    return bool(ch) and bool(_WORD_CHARS.fullmatch(ch))


def minify_whitespace(code: str) -> str:
    code = code.replace("\r", "")
    out: list[str] = []
    i = 0
    n = len(code)
    last_out = ""
    while i < n:
        ch = code[i]
        if ch.isspace():
            j = i + 1
            while j < n and code[j].isspace():
                j += 1
            next_ch = code[j] if j < n else ""
            if _is_word_char(last_out) and _is_word_char(next_ch):
                out.append(" ")
                last_out = " "
            i = j
            continue

        out.append(ch)
        last_out = ch
        i += 1
    return "".join(out)


def strip_c_like_comments(code: str) -> str:
    # Strips // and /* */ while preserving quoted strings (", ', `).
    out: list[str] = []
    i = 0
    n = len(code)
    in_squote = False
    in_dquote = False
    in_btick = False
    escape_next = False
    while i < n:
        ch = code[i]
        nxt = code[i + 1] if i + 1 < n else ""

        if escape_next:
            out.append(ch)
            escape_next = False
            i += 1
            continue

        if (in_squote or in_dquote or in_btick) and ch == "\\":
            out.append(ch)
            escape_next = True
            i += 1
            continue

        if not (in_squote or in_dquote or in_btick):
            if ch == "/" and nxt == "/":
                i += 2
                while i < n and code[i] not in ("\n", "\r"):
                    i += 1
                continue
            if ch == "/" and nxt == "*":
                i += 2
                while i + 1 < n and not (code[i] == "*" and code[i + 1] == "/"):
                    i += 1
                i = i + 2 if i + 1 < n else n
                continue

        if not (in_dquote or in_btick) and ch == "'" and not in_squote:
            in_squote = True
            out.append(ch)
            i += 1
            continue
        if in_squote and ch == "'":
            in_squote = False
            out.append(ch)
            i += 1
            continue

        if not (in_squote or in_btick) and ch == '"' and not in_dquote:
            in_dquote = True
            out.append(ch)
            i += 1
            continue
        if in_dquote and ch == '"':
            in_dquote = False
            out.append(ch)
            i += 1
            continue

        if not (in_squote or in_dquote) and ch == "`" and not in_btick:
            in_btick = True
            out.append(ch)
            i += 1
            continue
        if in_btick and ch == "`":
            in_btick = False
            out.append(ch)
            i += 1
            continue

        out.append(ch)
        i += 1
    return "".join(out)


def strip_hash_line_comments(code: str) -> str:
    # Best-effort for shell-like files; avoids stripping inside simple quotes/double quotes.
    out: list[str] = []
    i = 0
    n = len(code)
    in_squote = False
    in_dquote = False
    escape_next = False
    while i < n:
        ch = code[i]

        if escape_next:
            out.append(ch)
            escape_next = False
            i += 1
            continue

        if in_dquote and ch == "\\":
            out.append(ch)
            escape_next = True
            i += 1
            continue

        if not in_dquote and ch == "'" and not in_squote:
            in_squote = True
            out.append(ch)
            i += 1
            continue
        if in_squote and ch == "'":
            in_squote = False
            out.append(ch)
            i += 1
            continue

        if not in_squote and ch == '"' and not in_dquote:
            in_dquote = True
            out.append(ch)
            i += 1
            continue
        if in_dquote and ch == '"':
            in_dquote = False
            out.append(ch)
            i += 1
            continue

        if not (in_squote or in_dquote) and ch == "#":
            while i < n and code[i] not in ("\n", "\r"):
                i += 1
            continue

        out.append(ch)
        i += 1
    return "".join(out)


def strip_python_comments_and_docstrings(code: str) -> str:
    import io
    import token
    import tokenize

    src = code
    try:
        tok_iter = tokenize.generate_tokens(io.StringIO(src).readline)
    except Exception:
        return src

    out_parts: list[str] = []
    indent_stack: list[bool] = []
    at_module_start = True
    expect_docstring_after_indent = False
    pending_docstring_skip_newline = False

    def is_significant(tok_type: int) -> bool:
        return tok_type not in {
            tokenize.NL,
            tokenize.NEWLINE,
            tokenize.INDENT,
            tokenize.DEDENT,
            tokenize.COMMENT,
            tokenize.ENCODING,
        }

    for tok in tok_iter:
        tok_type = tok.type
        tok_str = tok.string

        if tok_type == tokenize.COMMENT:
            continue

        if tok_type == tokenize.INDENT:
            indent_stack.append(True)
            expect_docstring_after_indent = True
            out_parts.append(tok_str)
            continue

        if tok_type == tokenize.DEDENT:
            if indent_stack:
                indent_stack.pop()
            out_parts.append(tok_str)
            continue

        if pending_docstring_skip_newline and tok_type in {tokenize.NL, tokenize.NEWLINE}:
            pending_docstring_skip_newline = False
            continue

        if tok_type == tokenize.STRING:
            at_block_start = bool(indent_stack and indent_stack[-1])
            if at_module_start or expect_docstring_after_indent or at_block_start:
                pending_docstring_skip_newline = True
                at_module_start = False
                expect_docstring_after_indent = False
                if indent_stack:
                    indent_stack[-1] = False
                continue

        if tok_type == tokenize.NEWLINE or tok_type == tokenize.NL:
            out_parts.append(tok_str)
            continue

        if tok_type == token.NAME:
            if tok_str in {"def", "class"}:
                expect_docstring_after_indent = False

        if is_significant(tok_type):
            at_module_start = False
            if indent_stack:
                indent_stack[-1] = False
            expect_docstring_after_indent = False

        out_parts.append(tok_str)

    return "".join(out_parts)


def strip_license_header_like_block(code: str) -> str:
    # Heuristic: drop leading block comment if it mentions "license" or "copyright".
    head = code.lstrip()
    lowered = head[:4096].lower()
    if head.startswith("/*"):
        end = head.find("*/")
        if end != -1:
            block = head[: end + 2].lower()
            if "license" in block or "copyright" in block:
                return head[end + 2 :]
    if head.startswith("#"):
        lines = head.splitlines(True)
        acc: list[str] = []
        for ln in lines[:80]:
            if not ln.lstrip().startswith("#"):
                break
            acc.append(ln)
        block = "".join(acc).lower()
        if ("license" in block or "copyright" in block) and acc:
            return head[len("".join(acc)) :]
    return code


def minify_for_extension(path: Path, text: str) -> str:
    text = text.lstrip("\ufeff")
    text = strip_license_header_like_block(text)

    ext = path.suffix.lower()
    if ext == ".py":
        text = strip_python_comments_and_docstrings(text)
        return minify_whitespace(text)

    if ext in {".sh", ".bash", ".zsh"} or path.name.endswith(".sh"):
        text = strip_hash_line_comments(text)
        return minify_whitespace(text)

    if ext in {
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".mjs",
        ".cjs",
        ".java",
        ".c",
        ".cc",
        ".cpp",
        ".h",
        ".hpp",
        ".go",
        ".rs",
        ".cs",
        ".php",
        ".swift",
        ".kt",
        ".kts",
    }:
        text = strip_c_like_comments(text)
        return minify_whitespace(text)

    if ext in {".yaml", ".yml", ".toml", ".json"}:
        return minify_whitespace(text)

    return minify_whitespace(text)


def should_skip_path(
    path: Path,
    *,
    root: Path,
    exclude_dirs: set[str],
    exclude_files: set[str],
    exclude_suffixes: set[str],
) -> tuple[bool, str]:
    rel = path.relative_to(root)
    for part in rel.parts[:-1]:
        if part in exclude_dirs:
            return True, "excluded_dir"
        if part.startswith(".") and part not in {".env"}:
            return True, "dot_dir"

    name = path.name
    if name in exclude_files:
        return True, "excluded_file"
    if name.startswith(".") and name not in {".env", ".env.example"}:
        return True, "dot_file"
    if path.suffix.lower() in exclude_suffixes:
        return True, "excluded_suffix"
    return False, ""


@dataclass(frozen=True)
class IngestResult:
    files_included: int
    bytes_in: int
    bytes_out: int
    skipped: Counter[str]


def iter_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirpath_p = Path(dirpath)
        # Prune directories early
        dirnames[:] = [d for d in dirnames if d not in DEFAULT_EXCLUDE_DIRS and not d.startswith(".")]
        for fn in filenames:
            yield dirpath_p / fn


def ingest_to_xml(root: Path, out_path: Path, *, max_bytes: int) -> IngestResult:
    skipped: Counter[str] = Counter()
    files_included = 0
    bytes_in = 0
    bytes_out = 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n") as out_f:
        out_f.write("<r>\n")
        for file_path in iter_files(root):
            skip, reason = should_skip_path(
                file_path,
                root=root,
                exclude_dirs=DEFAULT_EXCLUDE_DIRS,
                exclude_files=DEFAULT_EXCLUDE_FILES,
                exclude_suffixes=DEFAULT_EXCLUDE_SUFFIXES,
            )
            if skip:
                skipped[reason] += 1
                continue

            try:
                data = file_path.read_bytes()
            except OSError:
                skipped["read_error"] += 1
                continue

            if len(data) > max_bytes:
                skipped["too_large"] += 1
                continue

            if is_probably_binary(data):
                skipped["binary"] += 1
                continue

            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    text = data.decode("utf-8", errors="replace")
                except Exception:
                    skipped["decode_error"] += 1
                    continue

            minified = minify_for_extension(file_path, text)
            minified = minified.strip()
            if not minified:
                skipped["empty_after_minify"] += 1
                continue

            rel = file_path.relative_to(root).as_posix()
            bytes_in += len(data)
            bytes_out += len(minified.encode("utf-8"))
            files_included += 1

            out_f.write('<f p="')
            out_f.write(xml_escape(rel, {'"': "&quot;"}))
            out_f.write('"><s>')
            out_f.write(xml_escape(minified))
            out_f.write("</s></f>\n")

        out_f.write("</r>\n")

    return IngestResult(
        files_included=files_included,
        bytes_in=bytes_in,
        bytes_out=bytes_out,
        skipped=skipped,
    )


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Generate minimalist XML (<r><f p=...><s>minified</s></f></r>) for repo ingestion."
    )
    ap.add_argument("--root", default=".", help="Repository root (default: .)")
    ap.add_argument("--out", default="", help="Output XML path (default: /tmp/<rootname>.min.xml)")
    ap.add_argument(
        "--max-bytes",
        type=int,
        default=750_000,
        help="Skip files larger than this many bytes (default: 750000)",
    )
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.exists() or not root.is_dir():
        print(f"ERROR: root not found: {root}", file=sys.stderr)
        return 2

    out_path = Path(args.out).expanduser() if args.out else Path("/tmp") / f"{root.name}.min.xml"
    out_path = out_path.resolve()

    res = ingest_to_xml(root, out_path, max_bytes=args.max_bytes)
    ratio = (res.bytes_out / res.bytes_in) if res.bytes_in else 0.0

    print(
        f"SUCCESS: wrote {out_path} | files={res.files_included} | in={res.bytes_in}B | out={res.bytes_out}B | ratio={ratio:.3f}"
    )
    if res.skipped:
        top = ", ".join(f"{k}={v}" for k, v in res.skipped.most_common(8))
        print(f"SKIPPED: {top}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

