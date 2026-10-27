"""Engineering identity versus interface compatibility; conservative on unknown rules."""
import ast
import hashlib
from functools import lru_cache
import io
import json
from pathlib import Path
import re
import tokenize

NON_RULE_REFS = {"workflow-handoff.md"}
INTERFACE_SECTIONS = {"参考文件", "与 ASG 的有状态工作流交接", "规则维护"}


def _hash(value):
    return hashlib.sha256(value).hexdigest()


def _digest(files):
    return _hash(json.dumps(files, sort_keys=True, separators=(",", ":")).encode())


def _usable(relative):
    return not (any(p.startswith(".") or p in {"tests", "__pycache__"} for p in relative.parts)
                or relative.suffix in {".pyc", ".pyo"} or relative.name.endswith("~"))


def _skill_body(text):
    if text.startswith("---\n"):
        text = text.split("\n---", 1)[-1]
    lines, skip = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            skip = line[3:].strip() in INTERFACE_SECTIONS
        if not skip:
            lines.append(line)
    return "\n".join(lines)


def _docstring_spans(tree):
    spans = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                spans.add((node.body[0].lineno, node.body[0].col_offset))
    return spans


def _code_tokens(raw):
    """Source tokens without comments, docstrings and blank lines.

    ``ast.dump`` output changes between interpreter versions (3.9 and 3.13 serialize the
    same tree differently), which made one unchanged SR look like changed rules. Token
    text is what the file says, so it hashes the same on every supported Python; f-strings,
    which 3.12+ tokenizes in pieces, are re-joined from the source so they hash as before.
    """
    text = raw.decode("utf-8")
    spans = _docstring_spans(ast.parse(text))
    lines = text.splitlines(keepends=True)
    out, fstring_start, depth = [], None, 0
    skip_until, drop_newline = None, False
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        kind, string, start, end = tok.type, tok.string, tok.start, tok.end
        if kind in (tokenize.COMMENT, tokenize.NL, tokenize.ENCODING, tokenize.ENDMARKER):
            continue
        name = tokenize.tok_name[kind]
        if name == "FSTRING_START":
            if depth == 0:
                fstring_start = start
            depth += 1
            continue
        if name == "FSTRING_END":
            depth -= 1
            if depth == 0:
                string, start, kind = _slice(lines, fstring_start, end), fstring_start, tokenize.STRING
            else:
                continue
        elif depth:
            continue   # pieces inside an f-string are covered by the joined slice
        if skip_until is not None:
            if start < skip_until:
                continue
            skip_until = None
        if kind == tokenize.STRING and start in spans:
            skip_until, drop_newline = end, True
            continue
        if kind == tokenize.NEWLINE and drop_newline:
            drop_newline = False   # the docstring statement's own line ending goes with it
            continue
        out.append((tokenize.tok_name[kind], string if kind != tokenize.NEWLINE else ""))
    return out


def _slice(lines, start, end):
    (l0, c0), (l1, c1) = start, end
    if l0 == l1:
        return lines[l0 - 1][c0:c1]
    return lines[l0 - 1][c0:] + "".join(lines[l0:l1 - 1]) + lines[l1 - 1][:c1]


@lru_cache(maxsize=4096)
def _normalized_hash(raw, suffix, entrypoint):
    """Cache by bytes, never timestamps; same-size replacements remain visible."""
    if suffix == ".py":
        try:
            return _hash(json.dumps(_code_tokens(raw), separators=(",", ":")).encode())
        except (SyntaxError, ValueError, tokenize.TokenError, UnicodeDecodeError):
            return _hash(b"invalid-python\0" + raw)  # Never silently ignore broken code.
    if suffix == ".md":
        text = raw.decode("utf-8")
        if entrypoint:
            text = _skill_body(text)
        # Ignore blank/trailing whitespace only; preserve quoted values, formula
        # spacing and code examples. Unknown substantive prose stays a rule.
        return _hash("\n".join(line.rstrip() for line in text.splitlines() if line.strip()).encode())
    return _hash(raw)


def engineering_identity(root):
    root = Path(root)
    paths = [root / "SKILL.md"]
    for directory in ("scripts", "references"):
        paths.extend(p for p in (root / directory).rglob("*") if p.is_file() and _usable(p.relative_to(root))
                     and not (directory == "references" and p.name in NON_RULE_REFS))
    files = {p.relative_to(root).as_posix(): _normalized_hash(p.read_bytes(), p.suffix, p.name == "SKILL.md") for p in sorted(paths)}
    return {"schema_version": 2, "digest": _digest(files), "files": files}

