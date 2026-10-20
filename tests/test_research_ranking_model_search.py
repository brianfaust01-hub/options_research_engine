import sys, unittest
from pathlib import Path
import numpy as np, pandas as pd
ROOT=Path(__file__).resolve().parent.parent; SRC=ROOT/"src"
if str(SRC) not in sys.path: sys.path.insert(0,str(SRC))
from research_ranking_model_search import _ridge_predict, discover_models, BASE_FEATURES

class ResearchRankingModelSearchTests(unittest.TestCase):
    def test_ridge_prediction_shape(self):
        x=np.arange(60,dtype=float).reshape(20,3); y=np.arange(20,dtype=float)
        self.assertEqual(_ridge_predict(x,y,x[:4],10,True).shape,(4,))
    def test_discovery_produces_date_holdout_models(self):
        rows=[]
        for day in range(4):
            for item in range(8):
                row={feature: float(item+day) for feature in BASE_FEATURES}
                row.update({"_Date":pd.Timestamp("2026-09-24")+pd.Timedelta(days=day),"_Return":(item-3)/100,"ResearchScore":50+item})
                rows.append(row)
        result=discover_models(pd.DataFrame(rows))
        self.assertEqual(result["dates"],4); self.assertEqual(len(result["candidates"]),12)
        self.assertIn("top3",result["candidates"][0])
if __name__=="__main__": unittest.main()
