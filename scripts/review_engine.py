"""Identity of engineering rules; interface docs/tests do not reopen electrical review."""
from pathlib import Path
from skill_identity import engineering_identity


def engine_identity(root=None):
    root = Path(root) if root else Path(__file__).resolve().parents[1]
    return engineering_identity(root)


def validate_engine(plan, require_current=False):
    identity = plan.get('review_engine')
    if not require_current:
        if identity is None or (isinstance(identity, dict) and identity.get('schema_version') in (1, 2)
                                and isinstance(identity.get('digest'), str) and isinstance(identity.get('files'), dict)):
            return []
        return ['review_engine: malformed SR rule fingerprint']
    if identity != engine_identity():
        return ['review_engine: absent, legacy identity or changed engineering rules; regenerate under current SR']
    return []
