import json
from pathlib import Path
import numpy as np
import pandas as pd
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"src"))
from six_week_calibration import fit,predict,training_before,shadow,review_forward,VERSION


def fixture_frame():
    return pd.DataFrame({'RecommendationID':['a','b','c','d'],'_Date':pd.to_datetime(['2026-10-01','2026-10-02','2026-10-05','2026-10-06']),
      'Horizon7DEvaluationDate':['2026-10-12','2026-10-13','2026-10-14','2026-10-15'],
      'ResearchScore':[70,80,90,95],'Direction':['BEARISH','BULLISH','BEARISH','BULLISH'],'_Return':[-.01,.02,-.03,.04]})


class CalibrationTests(unittest.TestCase):
    def test_training_purges_not_yet_mature_and_embargo_day(self):
        f=fixture_frame(); train=training_before(f,'2026-10-15')
        assert train.RecommendationID.tolist()==['a','b']
        # Modifying future outcomes cannot alter the fitted parameters.
        f.loc[2:,'_Return']=999
        assert fit(train)==fit(training_before(f,'2026-10-15'))


    def test_probabilities_finite_and_fit_reproducible(self):
        f=fixture_frame();p=predict(f,fit(f))
        assert np.isfinite(p).all() and ((p>0)&(p<1)).all()
        assert np.array_equal(p,predict(f,fit(f)))


    def test_invalid_score_and_direction_rejected(self):
        f=fixture_frame();f.loc[0,'ResearchScore']=101
        with self.assertRaises(ValueError): fit(f)
        f.loc[0,'ResearchScore']=80;f.loc[0,'Direction']='UNKNOWN'
        with self.assertRaises(ValueError): fit(f)


    def test_forward_shadow_is_separate_and_latest_only(self):
        f=fixture_frame();f['RecommendationDate']=['2026-11-02','2026-11-02','2026-11-03','2026-11-03']
        f['Direction']=f.Direction.str.title()
        f['action']='Evaluate Options';f['opportunity_type']='Candidate';f['option_strategy']='Long Call'
        original=f.copy(deep=True)
        m={'version':VERSION,'mode':'SHADOW_ONLY','coefficients':fit(f),'activation_not_before':'2026-11-01','training_latest_outcome':'2026-10-29','target':'underlying'}
        out=shadow(f,m)
        assert set(out.RecommendationID)=={'c','d'}
        assert out.ShadowMode.eq('FORWARD_SHADOW').all()
        pd.testing.assert_frame_equal(f,original)
        m['activation_not_before']='2026-11-04'
        with self.assertRaises(ValueError): shadow(f,m)
        m['activation_not_before']='2026-11-01';m['training_latest_outcome']='2026-11-03'
        with self.assertRaises(ValueError): shadow(f,m)

class ForwardReviewTests(unittest.TestCase):
    def test_censoring_duplicate_reruns_and_no_promotion(self):
        p=pd.DataFrame({'RecommendationID':['a','b','a'],'RecommendationDate':['2026-11-02']*3,'ShadowPolicyVersion':[VERSION]*3,'ShadowProbability':[.6,.7,.6],'ShadowBaseRate':[.54]*3})
        h=pd.DataFrame({'RecommendationID':['a','b'],'Horizon7DEvaluationDate':['2026-11-11','2026-11-12'],'Horizon7DDirectionalReturnPct':[.01,-.02]})
        r=review_forward(p,h,'2026-11-11')
        self.assertEqual(r['saved_unique_predictions'],2)
        self.assertEqual(r['matured'],1)
        self.assertEqual(r['censored_or_missing'],1)
        self.assertFalse(r['automatic_promotion'])
        p.loc[2,'ShadowProbability']=.9
        with self.assertRaises(ValueError):review_forward(p,h,'2026-11-12')


if __name__=="__main__": unittest.main()
