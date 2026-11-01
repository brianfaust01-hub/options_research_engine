import sys,unittest
from pathlib import Path
from unittest.mock import patch
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'src'))
from configuration_profile_shadow import profile_flags,allocate_profile


class ProfileTests(unittest.TestCase):
    def test_joint_conditions_units_boundaries_and_missing(self):
        f=pd.DataFrame({'ResearchScore':[95,95,80,80,95],'theta_drag_pct_per_day':[.009,.01,None,None,-.01],'broker_delta':[.6,.35,-.5,.45,None],'implied_volatility':[.5,.3,.4,.2,None]})
        flags=profile_flags(f)
        self.assertEqual(flags.QualityDecayProfile.tolist(),[True,False,False,False,False])
        self.assertEqual(flags.ModerateDeltaIVProfile.tolist(),[False,False,True,False,False])
        self.assertEqual(flags.QualityOrContractProfile.tolist(),[True,False,True,False,False])

    def test_isolated_copy_and_original_safety_inputs(self):
        f=pd.DataFrame({'ResearchScore':[95,80],'theta_drag_pct_per_day':[.005,.02],'action':['Evaluate Options']*2,'execution_score':[50,90]})
        original=f.copy(deep=True);positions=pd.DataFrame({'contracts':[1]});original_positions=positions.copy(deep=True)
        with patch('configuration_profile_shadow.arbitrate_portfolio',return_value='fixture') as allocate:
            self.assertEqual(allocate_profile(f,positions,policy='quality_decay',account_nav=15000),'fixture')
            submitted=allocate.call_args.args[0]
            self.assertEqual(submitted.action.tolist(),['Evaluate Options','Watch'])
            # A good research profile never upgrades a bad execution score.
            self.assertEqual(submitted.execution_score.tolist(),[50,90])
            self.assertEqual(allocate.call_args.kwargs['paper_trading'],True)
        pd.testing.assert_frame_equal(f,original);pd.testing.assert_frame_equal(positions,original_positions)

    def test_baseline_does_not_filter(self):
        f=pd.DataFrame({'action':['Evaluate Options']})
        with patch('configuration_profile_shadow.arbitrate_portfolio') as allocate:
            allocate_profile(f,pd.DataFrame(),policy='baseline',account_nav=15000)
            self.assertEqual(allocate.call_args.args[0].action.iloc[0],'Evaluate Options')
        with self.assertRaises(ValueError):allocate_profile(f,pd.DataFrame(),policy='unknown',account_nav=15000)


if __name__=='__main__':unittest.main()
