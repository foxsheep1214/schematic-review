"""Content identity of the rules actually used, including uncommitted edits."""
import hashlib
import json
from pathlib import Path


def _rule_file(relative):
    # Finder/editor/test byproducts are not rules; hidden names include .DS_Store and .pytest_cache.
    parts = relative.parts
    return not (any(x.startswith('.') or x in ('tests', '__pycache__') for x in parts)
                or relative.suffix in ('.pyc', '.pyo') or relative.name.endswith('~'))


def engine_identity(root=None):
    root = Path(root) if root else Path(__file__).resolve().parents[1]
    paths = [root / 'SKILL.md']
    for directory in ('scripts', 'references'):
        paths.extend(p for p in (root / directory).rglob('*') if p.is_file() and _rule_file(p.relative_to(root)))
    files = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(paths)}
    encoded = json.dumps(files, sort_keys=True, separators=(',', ':')).encode()
    return {'schema_version': 1, 'digest': hashlib.sha256(encoded).hexdigest(), 'files': files}


def validate_engine(plan, require_current=False):
    identity = plan.get('review_engine')
    if not require_current:
        # Historical record validation only; CLI release always requires current rules.
        if identity is None or (isinstance(identity, dict) and identity.get('schema_version') == 1
                                and isinstance(identity.get('digest'), str) and isinstance(identity.get('files'), dict)):
            return []
        return ['review_engine: malformed SR rule fingerprint']
    if identity != engine_identity():
        return ['review_engine: absent or changed SR rules; regenerate plan and review under current SR']
    return []
