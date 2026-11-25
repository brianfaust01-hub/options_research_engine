"""Preserving daily-collector recovery; frozen collection source stays intact."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4
from option_observation_collector import ROOT,DEFAULT_OUTPUT,collect,timestamp
import option_observation_collector as frozen_collector


def atomic_save_new(path,payload):
    """Commit complete new artifacts; interrupted temporaries are never samples."""
    path=Path(path)
    if path.exists():raise FileExistsError(path)
    temporary=path.with_name('.'+path.name+'.'+uuid4().hex+'.tmp')
    with temporary.open('x',encoding='utf-8') as handle:
        json.dump(payload,handle,indent=2,allow_nan=False)
        handle.flush();os.fsync(handle.fileno())
    # Supported runtime is Windows: rename is atomic and fails if target exists.
    if path.exists():raise FileExistsError(path)
    temporary.rename(path)


@contextmanager
def atomic_artifacts():
    """Process-local IO adapter only; restore the frozen module after collection.

    The normal daily collector runs in its own subprocess. Its normalization,
    sampling, quotes and rules are unchanged; no shadow process imports this adapter.
    """
    original=frozen_collector.save_new
    frozen_collector.save_new=atomic_save_new
    try:yield
    finally:frozen_collector.save_new=original


def inspect_history(directory):
    bad=[];valid=0
    for path in sorted(Path(directory).glob('sample_*.json')):
        payload=path.read_bytes()
        try:
            bundle=json.loads(payload.decode('utf-8'))
            observations=bundle['observations']
            if not isinstance(observations,list):raise ValueError('Invalid observation list')
            for row in observations:
                if not isinstance(row,dict) or not isinstance(row.get('quote_status'),str):
                    raise ValueError('Invalid observation row')
                if row['quote_status']=='OBSERVED' and (
                    not isinstance(row.get('contract_symbol'),str) or not row['contract_symbol'].strip()
                    or not isinstance(row.get('observed_at'),str) or timestamp(row.get('observed_at')) is None):
                    raise ValueError('Invalid observed identity or receipt time')
            valid+=1
        except (ValueError,UnicodeError,KeyError,TypeError) as exc:
            bad.append(dict(path=str(path.resolve()),sha256=hashlib.sha256(payload).hexdigest(),
                bytes=len(payload),error_type=type(exc).__name__,
                line=getattr(exc,'lineno',None),column=getattr(exc,'colno',None)))
    return dict(valid_bundles=valid,invalid_bundles=bad)


def recover_history(directory,*,now=None):
    root=Path(directory).resolve();root.mkdir(parents=True,exist_ok=True)
    now=now or datetime.now(timezone.utc)
    report=inspect_history(root);completed=[]
    for item in report['invalid_bundles']:
        source=Path(item['path']).resolve()
        quarantine=root/'quarantine';quarantine.mkdir(exist_ok=True)
        identifier=uuid4().hex
        target=(quarantine/(identifier+'_'+source.name)).resolve()
        # Validate resolved Windows move targets before moving any artifact.
        if source.parent!=root or target.parent!=quarantine.resolve() or not target.is_relative_to(root):
            raise ValueError('Quarantine path escapes observation directory')
        if now.timestamp()-source.stat().st_mtime<300:
            raise ValueError('Unreadable observation may still be actively written; recovery deferred')
        if hashlib.sha256(source.read_bytes()).hexdigest()!=item['sha256']:
            raise ValueError('Observation changed during recovery; leave it untouched')
        plan={**item,'status':'QUARANTINE_PLANNED','original_path':str(source),'preserved_path':str(target),
            'at':now.isoformat(),'reason':'Unreadable historical collection artifact; preserve bytes, never infer replacement quotes'}
        manifest=quarantine/(identifier+'.planned.json')
        atomic_save_new(manifest,plan)
        source.rename(target)
        if hashlib.sha256(target.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('Quarantine hash mismatch')
        done={**plan,'status':'QUARANTINED_BYTES_VERIFIED','plan_manifest':str(manifest)}
        atomic_save_new(quarantine/(identifier+'.completed.json'),done)
        completed.append(done)
    return dict(valid_bundles=report['valid_bundles'],quarantined_bundles=len(completed),records=completed)


def run(journal,output=DEFAULT_OUTPUT,*,fetch=None,now=None):
    recovery=recover_history(output,now=now)
    with atomic_artifacts():summary=collect(journal,output,fetch=fetch,now=now)
    result={**summary,'history_recovery':recovery}
    atomic_save_new(Path(output)/('recovery_'+uuid4().hex+'.json'),result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--journal',type=Path,default=ROOT/'data/trade_journal.csv')
    p.add_argument('--output-dir',type=Path,default=DEFAULT_OUTPUT)
    p.add_argument('--inspect-only',action='store_true')
    a=p.parse_args()
    result=inspect_history(a.output_dir) if a.inspect_only else run(a.journal,a.output_dir)
    print('Option research collection: '+json.dumps(result))
