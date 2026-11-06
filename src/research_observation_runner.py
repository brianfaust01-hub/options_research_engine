"""Bounded post-priority collectors; independent of frozen trading kernels."""
import json
from pathlib import Path
from structure_research import collect,publish_report
from spy_vix_context import capture,publish as publish_vix


if __name__=='__main__':
    for name,operation in [('structures',collect),('spy_vix',capture)]:
        try:
            result=operation()
            print(json.dumps({'research':name,'status':result.get('status')}))
        except Exception as exc:
            print(json.dumps({'research':name,'status':'FAILED','error_type':type(exc).__name__}))
    try:publish_report(Path(__file__).resolve().parent.parent)
    except Exception as exc:print(json.dumps({'research':'structures_report','status':'FAILED','error_type':type(exc).__name__}))
    try:publish_vix(Path(__file__).resolve().parent.parent)
    except Exception as exc:print(json.dumps({'research':'spy_vix_report','status':'FAILED','error_type':type(exc).__name__}))
