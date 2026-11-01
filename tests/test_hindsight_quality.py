import sys,unittest
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'src'))
from hindsight_quality import reviewed_quality_view


class HindsightQualityTests(unittest.TestCase):
    def test_both_directions_excluded_without_source_mutation(self):
        f=pd.DataFrame({'RecommendationID':['a','b','c','d'],'Ticker':['CTVA','CTVA','CTVA','OTHER'],'RecommendationDate':['2026-09-24','2026-09-25','2026-10-01','2026-09-24'],'Direction':['BULLISH','BEARISH','BULLISH','BEARISH'],'Return':[.9,-.8,.02,.01]})
        original=f.copy(deep=True);view,audit=reviewed_quality_view(f)
        self.assertEqual(view.RecommendationID.tolist(),['c','d'])
        self.assertEqual(audit.RecommendationID.tolist(),['a','b'])
        pd.testing.assert_frame_equal(f,original)
        view2,audit2=reviewed_quality_view(view)
        pd.testing.assert_frame_equal(view,view2)
        self.assertTrue(audit2.empty)

    def test_missing_schema_fails_closed(self):
        with self.assertRaises(ValueError):reviewed_quality_view(pd.DataFrame({'Return':[1]}))


if __name__=='__main__':unittest.main()
