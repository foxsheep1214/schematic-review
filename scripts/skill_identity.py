"""Engineering identity versus interface compatibility; conservative on unknown rules."""
import ast
import hashlib
from functools import lru_cache
import json
from pathlib import Path
import re

NON_RULE_REFS = {"workflow-handoff.md", "improvement-ledger.md", "release-validation.md",
                 "upstream-integration.md", "upstream-sources.json"}
INTERFACE_SECTIONS = {"参考文件", "有状态工作流交接", "与 ASG 的有状态工作流交接", "规则维护"}


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


class _StripDocs(ast.NodeTransformer):
    def generic_visit(self, node):
        super().generic_visit(node)
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                node.body = node.body[1:]
        return node


@lru_cache(maxsize=4096)
def _normalized_hash(raw, suffix, entrypoint):
    """Cache by bytes, never timestamps; same-size replacements remain visible."""
    if suffix == ".py":
        try:
            tree = _StripDocs().visit(ast.parse(raw))
            return _hash(ast.dump(tree, include_attributes=False).encode())
        except (SyntaxError, ValueError):
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
                     and not (directory == "references" and
                              (p.name in NON_RULE_REFS or "upstream-licenses" in p.parts)))
    files = {p.relative_to(root).as_posix(): _normalized_hash(p.read_bytes(), p.suffix, p.name == "SKILL.md") for p in sorted(paths)}
    return {"schema_version": 2, "digest": _digest(files), "files": files}


def compatibility_identity(root):
    root = Path(root)
    paths = [root / "SKILL.md"]
    for name in ("README.md", "references/workflow-handoff.md", "agents/openai.yaml"):
        p = root / name
        if p.is_file():
            paths.append(p)
    return _digest({p.relative_to(root).as_posix(): _hash(p.read_bytes()) for p in sorted(paths)})
