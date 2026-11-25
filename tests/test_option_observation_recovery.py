from datetime import datetime,timedelta,timezone
import hashlib
import csv
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import option_observation_recovery as m

NOW=datetime(2026,11,24,22,tzinfo=timezone.utc)


class ObservationRecoveryTests(unittest.TestCase):
    def test_corrupt_history_is_preserved_and_valid_sources_unchanged(self):
        with TemporaryDirectory() as d:
            root=Path(d);bad=root/'sample_bad.json';bad.write_bytes(b'{"observations":[')
            old=(NOW-timedelta(hours=1)).timestamp();os.utime(bad,(old,old))
            valid=root/'sample_good.json';valid.write_text(json.dumps({'observations':[{'quote_status':'MISSING_QUOTE'}]}))
            before=valid.read_bytes();digest=hashlib.sha256(bad.read_bytes()).hexdigest()
            r=m.recover_history(root,now=NOW)
            self.assertEqual(r['quarantined_bundles'],1)
            self.assertFalse(bad.exists())
            preserved=Path(r['records'][0]['preserved_path'])
            self.assertEqual(hashlib.sha256(preserved.read_bytes()).hexdigest(),digest)
            self.assertEqual(valid.read_bytes(),before)
            self.assertEqual(m.inspect_history(root)['invalid_bundles'],[])
            self.assertEqual(m.recover_history(root,now=NOW)['quarantined_bundles'],0)
            self.assertEqual(len(list((root/'quarantine').glob('*.planned.json'))),1)
            self.assertEqual(len(list((root/'quarantine').glob('*.completed.json'))),1)

    def test_fresh_partial_file_is_not_moved_while_writer_may_be_active(self):
        with TemporaryDirectory() as d:
            root=Path(d);bad=root/'sample_bad.json';bad.write_bytes(b'{')
            os.utime(bad,(NOW.timestamp(),NOW.timestamp()))
            with self.assertRaisesRegex(ValueError,'actively written'):m.recover_history(root,now=NOW)
            self.assertEqual(bad.read_bytes(),b'{')

    def test_schema_failure_and_malformed_observed_identity_are_detected(self):
        with TemporaryDirectory() as d:
            root=Path(d)
            for i,payload in enumerate(({'observations':{}},{'observations':[{'quote_status':'OBSERVED'}]},
                {'observations':[{'quote_status':'OBSERVED','contract_symbol':'TEST','observed_at':1234567890}]})):
                (root/f'sample_{i}.json').write_text(json.dumps(payload))
            (root/'sample_bom.json').write_bytes(b'\xef\xbb\xbf{"observations":[]}')
            self.assertEqual(len(m.inspect_history(root)['invalid_bundles']),4)

    def test_daily_runner_recovers_before_delegating_to_frozen_collector(self):
        with TemporaryDirectory() as d:
            root=Path(d);bad=root/'sample_bad.json';bad.write_bytes(b'{')
            old=(NOW-timedelta(hours=1)).timestamp();os.utime(bad,(old,old))
            def collect(*args,**kwargs):
                self.assertFalse(bad.exists())
                return dict(status='COMPLETE',production_policy_changed=False)
            with patch.object(m,'collect',side_effect=collect):result=m.run(root/'journal.csv',root,now=NOW)
            self.assertEqual(result['history_recovery']['quarantined_bundles'],1)
            self.assertEqual(result['status'],'COMPLETE')

    def test_atomic_writer_never_exposes_partial_json_as_a_sample(self):
        with TemporaryDirectory() as d:
            root=Path(d);path=root/'sample_new.json'
            with self.assertRaises(ValueError):m.atomic_save_new(path,dict(value=float('nan')))
            self.assertFalse(path.exists())
            self.assertEqual(list(root.glob('sample_*.json')),[])
            m.atomic_save_new(path,dict(observations=[]))
            original=path.read_bytes()
            with self.assertRaises(FileExistsError):m.atomic_save_new(path,dict(changed=True))
            self.assertEqual(path.read_bytes(),original)

    def test_io_adapter_restores_frozen_function_after_failure(self):
        original=m.frozen_collector.save_new
        with self.assertRaises(RuntimeError):
            with m.atomic_artifacts():
                self.assertIs(m.frozen_collector.save_new,m.atomic_save_new)
                raise RuntimeError('fixture interrupted')
        self.assertIs(m.frozen_collector.save_new,original)

    def test_real_collector_can_save_new_samples_after_recovery_without_network(self):
        with TemporaryDirectory() as d:
            root=Path(d);journal=root/'journal.csv';symbol='AAPL  270115C00100000'
            row=dict(RecommendationID='R1',RecommendationDate='2026-11-24T15:00:00+00:00',
                ticker='AAPL',option_strategy='Long Call',contract_symbol=symbol,expiration='2027-01-15')
            with journal.open('w',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=list(row));writer.writeheader();writer.writerow(row)
            bad=root/'sample_bad.json';bad.write_bytes(b'{')
            old=(NOW-timedelta(hours=1)).timestamp();os.utime(bad,(old,old))
            def fetch(symbols,**kwargs):
                return {symbol:dict(realtime=True,quote=dict(bidPrice=1,askPrice=1.1,
                    quoteTime=NOW.timestamp()*1000,volatility=30))}
            result=m.run(journal,root,fetch=fetch,now=NOW)
            self.assertEqual(result['status'],'COMPLETE')
            self.assertEqual(result['quote_status_counts'],{'OBSERVED':1})
            self.assertEqual(m.inspect_history(root)['invalid_bundles'],[])


if __name__=='__main__':unittest.main()
