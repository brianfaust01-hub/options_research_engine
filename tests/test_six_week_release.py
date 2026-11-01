import json,sys,tempfile,unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'src'))
from six_week_release import active_settings,RELATIVE_SETTINGS
import daily_run


class ReleaseTests(unittest.TestCase):
    def test_disabled_and_date_gated(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.assertEqual(active_settings(root),{})
            p=root/RELATIVE_SETTINGS;p.parent.mkdir(parents=True)
            p.write_text(json.dumps({'enabled':False}))
            self.assertEqual(active_settings(root,date(2026,11,2)),{})
            p.write_text(json.dumps({'enabled':True}))
            with self.assertRaises(ValueError):active_settings(root,date(2026,10,30))
            with self.assertRaises(FileNotFoundError):active_settings(root,date(2026,11,2))
            (p.parent/'challenger.json').write_text('{}')
            self.assertTrue(active_settings(root,date(2026,11,2))['quality_review'])

    def test_disabled_integration_launches_nothing(self):
        with patch('six_week_release.active_settings',return_value={}), patch.object(daily_run.subprocess,'run') as run:
            daily_run.refresh_six_week_shadow()
            run.assert_not_called()

    def test_shadow_failure_does_not_raise_or_send_email(self):
        with patch('six_week_release.active_settings',return_value={'model':'fixture.json'}),patch.object(daily_run.subprocess,'run',side_effect=OSError('fixture')),patch.object(daily_run,'send_email_report') as email:
            daily_run.refresh_six_week_shadow()
            email.assert_not_called()


if __name__=='__main__':unittest.main()
