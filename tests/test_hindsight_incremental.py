import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import research_hindsight as engine
from hindsight_incremental import VERSION, HORIZONS, fingerprint, frozen, prior_for, preserve_completed, reusable_horizon, load_previous


class IncrementalHindsightTests(unittest.TestCase):
    def row(self):
        return pd.Series({'RecommendationID':'A','RecommendationDate':'2026-01-02T10:30:00',
            'ticker':'TEST','action':'Buy','opportunity_type':'Call','option_strategy':'Long Call','EntryUnderlyingPrice':100.})

    def data(self):
        idx=pd.bdate_range('2026-01-02',periods=75)
        return pd.DataFrame({('Close','TEST'):[100+i for i in range(75)],('Close','SPY'):[100+i/2 for i in range(75)]},index=idx)

    def completed(self):
        return engine._evaluate_recommendation(self.row(),self.data(),self.data()[('Close','SPY')],pd.Timestamp('2026-05-01'))

    def test_finished_record_frozen_only_after_all_horizons_and_final(self):
        old=self.completed(); self.assertTrue(frozen(old))
        old['Horizon30DStatus']='IN_PROGRESS'; self.assertFalse(frozen(old))

    def test_input_changes_invalidate_reuse(self):
        row=self.row(); old=self.completed()|{'HindsightCacheVersion':VERSION,'HindsightInputFingerprint':fingerprint(row)}
        self.assertIsNotNone(prior_for(row,{'A':old}))
        changed=row.copy(); changed['EntryUnderlyingPrice']=120.
        self.assertIsNone(prior_for(changed,{'A':old}))

    def test_legacy_identity_checks(self):
        old=self.completed(); self.assertIsNotNone(prior_for(self.row(),{'A':old}))
        self.assertIsNone(prior_for(self.row(),{'A':old|{'Ticker':'OTHER'}}))

    def test_completed_horizon_survives_missing_or_revised_provider(self):
        old=self.completed(); result=preserve_completed({'Horizon7DStatus':'IN_PROGRESS'},old)
        self.assertEqual(result['Horizon7DDirectionalReturnPct'],old['Horizon7DDirectionalReturnPct'])
        self.assertFalse(reusable_horizon(old|{'Horizon7DSPYReturnPct':None},7))

    def test_pending_long_horizon_skips_completed_short_horizon_calculations(self):
        old=self.completed(); old['Horizon30DStatus']='IN_PROGRESS'
        calls=[]; original=engine._evaluate_fixed_horizon
        def evaluate(**kwargs): calls.append(kwargs['trading_days']); return original(**kwargs)
        with patch.object(engine,'_evaluate_fixed_horizon',side_effect=evaluate):
            result=engine._evaluate_recommendation(self.row(),self.data(),self.data()[('Close','SPY')],pd.Timestamp('2026-05-02'),cached=old)
        self.assertEqual(calls,[30])
        self.assertEqual(result['Horizon7DDirectionalReturnPct'],old['Horizon7DDirectionalReturnPct'])

    def test_repeat_generation_fetches_nothing_and_rebuild_is_explicit(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp); journal=root/'journal.csv'; self.row().to_frame().T.to_csv(journal,index=False)
            out=root/'processed'
            with patch.object(engine,'JOURNAL_PATH',journal),patch.object(engine,'PROCESSED_DATA_DIR',out),patch.object(engine,'_download_prices',return_value=self.data()) as fetch:
                first=engine.generate_research_hindsight()
                raw=Path(first['output_path']).read_bytes()
                self.assertEqual(fetch.call_count,1)
                with patch.object(engine,'_evaluate_recommendation',side_effect=AssertionError('Frozen row recalculated')):
                    second=engine.generate_research_hindsight()
                self.assertEqual(fetch.call_count,1)
                self.assertEqual(second['incremental']['reused_complete_rows'],1)
                self.assertEqual(Path(first['output_path']).read_bytes(),raw)
                rebuilt=engine.generate_research_hindsight(rebuild=True)
                self.assertEqual(fetch.call_count,2)
                self.assertEqual(rebuilt['incremental']['mode'],'FULL_REBUILD')

    def test_legacy_seed_preserves_values_and_source(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp); journal=root/'journal.csv'; self.row().to_frame().T.to_csv(journal,index=False)
            old=root/'research_hindsight_old.csv'; pd.DataFrame([self.completed()]).to_csv(old,index=False)
            raw=old.read_bytes()
            with patch.object(engine,'JOURNAL_PATH',journal),patch.object(engine,'PROCESSED_DATA_DIR',root),patch.object(engine,'_download_prices',side_effect=AssertionError('Mature legacy fetch')):
                result=engine.generate_research_hindsight()
            self.assertTrue(result['incremental']['legacy_seed_identity_only'])
            self.assertEqual(old.read_bytes(),raw)
            frame=pd.read_csv(result['output_path'])
            self.assertAlmostEqual(frame.iloc[0]['Horizon7DDirectionalReturnPct'],self.completed()['Horizon7DDirectionalReturnPct'])

    def test_checksum_failure_is_visible(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp); file=root/'research_hindsight_test.csv'
            pd.DataFrame([self.completed()|{'HindsightCacheVersion':VERSION}]).to_csv(file,index=False)
            file.with_suffix('.manifest.json').write_text('{"output_sha256":"wrong"}')
            with self.assertRaisesRegex(ValueError,'checksum'): load_previous(root)


if __name__=='__main__': unittest.main()
