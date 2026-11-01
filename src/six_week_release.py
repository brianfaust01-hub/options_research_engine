"""Local, explicit activation gate for the Sunday shadow release."""
from __future__ import annotations
import json
from datetime import date, datetime
from zoneinfo import ZoneInfo
from pathlib import Path

RELATIVE_SETTINGS=Path('research/six_week_20261029/activation.json')


def active_settings(root, today=None):
    p=Path(root)/RELATIVE_SETTINGS
    if not p.exists():return {}
    settings=json.loads(p.read_text(encoding='utf-8-sig'))
    if not settings.get('enabled',False):return {}
    if (today or datetime.now(ZoneInfo('America/New_York')).date())<date(2026,11,1):raise ValueError('Sunday shadow activation is not yet eligible')
    comparison=bool(settings.get('comparison_enabled',False))
    diagnostic=bool(settings.get('diagnostic_forecast',not comparison))
    if comparison and settings.get('release_status')!='READY':raise ValueError('Trading comparison release is not ready')
    result={'quality_review':bool(settings.get('quality_review',True)),'comparison':comparison}
    if diagnostic:
        model=Path(root)/'research/six_week_20261029/challenger.json'
        if not model.exists():raise FileNotFoundError('Frozen challenger artifact missing')
        result['model']=str(model)
    return result
