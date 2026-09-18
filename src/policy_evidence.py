"""Forward policy provenance only; no historical rewrites or trading decisions."""
from __future__ import annotations

import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULE_FILES = ('config.py', 'exit_rules.py', 'decision_enrichment.py', 'trade_scoring.py',
              'portfolio_allocator.py', 'portfolio_arbitrator.py',
              'option_selector.py', 'options_engine.py', 'position_sizing.py',
              'trade_constructor.py', 'opportunity_engine.py', 'research_engine.py')


def capture_policy_evidence(root=ROOT):
    """Archive static scalar settings and exact approved rule sources locally.

    Never visits OAuth files, environment variables, or account data. Config
    source itself is not copied because users may put credentials in it.
    """
    root = Path(root)
    src = root / 'src'
    settings = {}
    for node in ast.parse((src / 'config.py').read_text(encoding='utf-8-sig')).body:
        if not isinstance(node, ast.Assign):
            continue
        try:
            v = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name) or not target.id.isupper():
                continue
            name = target.id
            if any(term in name for term in ('SECRET', 'TOKEN', 'PASSWORD', 'CREDENTIAL', 'CLIENT_', 'API_KEY')):
                continue
            if isinstance(v, (int, float, bool)) or name in {'VERSION', 'CONFIG_VERSION', 'POLICY_ERA_ID', 'POLICY_ERA_BASELINE_DATE', 'SHADOW_EXIT_POLICY_VERSION', 'RESEARCH_PRICE_METHOD', 'EXECUTION_ENTRY_METHOD', 'EXECUTION_EXIT_METHOD', 'MIN_EXECUTION_GRADE'}:
                settings[name] = v
    hashes, sources, missing = {}, {}, []
    for name in RULE_FILES:
        path = src / name
        if not path.exists():
            missing.append(name)
            continue
        content = path.read_text(encoding='utf-8-sig')
        hashes[name] = hashlib.sha256(content.encode()).hexdigest()
        if name != 'config.py':
            sources[name] = content
    identity = {'schema_version': 1, 'settings': settings, 'source_sha256': hashes,
                'settings_definition': 'STATIC_LITERALS_NOT_RUNTIME_OVERRIDES',
                'missing_rule_files': missing}
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    directory = root / 'data' / 'processed' / 'policy_evidence'
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f'{digest}.json'
    if not path.exists():
        try:
            with path.open('x', encoding='utf-8') as handle:
                json.dump({**identity, 'fingerprint': digest,
                    'captured_at': datetime.now(timezone.utc).isoformat(),
                    'rule_sources': sources,
                    'limitation': 'Fingerprint is provenance, not a new policy era or a complete portfolio replay.'}, handle, indent=2)
        except FileExistsError:
            pass
    return {'PolicyEvidenceFingerprint': digest,
            'PolicyEvidencePath': str(path.relative_to(root)),
            'PolicyEvidenceStatus': 'CAPTURED' if not missing else 'PARTIAL_RULE_COVERAGE'}
