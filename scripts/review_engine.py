"""Content identity of the rules actually used, including uncommitted edits."""
import hashlib
import json
from pathlib import Path


def engine_identity(root=None):
    root = Path(root) if root else Path(__file__).resolve().parents[1]
    paths = [root / 'SKILL.md']
    for directory in ('scripts', 'references'):
        paths.extend(p for p in (root / directory).rglob('*') if p.is_file()
                     and not any(x in p.relative_to(root).parts for x in
                                 ('tests', '__pycache__', '.pytest_cache')))
    files = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(paths)}
    encoded = json.dumps(files, sort_keys=True, separators=(',', ':')).encode()
    return {'schema_version': 1, 'digest': hashlib.sha256(encoded).hexdigest(), 'files': files}


def validate_engine(plan, require_current=False):
    identity = plan.get('review_engine')
    if identity is None and not require_current:
        return []  # Historical record validation only; CLI release always requires current rules.
    if identity != engine_identity():
        return ['review_engine: absent or changed SR rules; regenerate plan and review under current SR']
    return []
