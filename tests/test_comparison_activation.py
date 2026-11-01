import json,os,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'src'))
from six_week_release import active_settings
from datetime import date


class ActivationTests(unittest.TestCase):
    def test_comparison_gate_needs_ready_scope_and_no_forecast_model(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=root/'research/six_week_20261029/activation.json';p.parent.mkdir(parents=True)
            value={'enabled':True,'comparison_enabled':True,'diagnostic_forecast':False,'release_status':'REVIEW'};p.write_text(json.dumps(value))
            with self.assertRaises(ValueError):active_settings(root,date(2026,11,2))
            value['release_status']='READY';p.write_text(json.dumps(value))
            settings=active_settings(root,date(2026,11,2));self.assertTrue(settings['comparison']);self.assertNotIn('model',settings)

    @unittest.skipUnless(shutil.which('powershell.exe'),'PowerShell required')
    def test_rollback_preserves_comparison_flags_and_bad_release_cannot_enable(self):
        root_source=Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as d:
            release=Path(d)/'research/six_week_20261029';release.mkdir(parents=True)
            script=release/'Set-ShadowRelease.ps1';script.write_bytes((root_source/'research/six_week_20261029/Set-ShadowRelease.ps1').read_bytes())
            settings={'enabled':True,'quality_review':True,'comparison_enabled':True,'diagnostic_forecast':False,'release_status':'READY'}
            p=release/'activation.json';p.write_text(json.dumps(settings))
            (release/'release_manifest.json').write_text('{"version":"INVALID","files":[]}')
            cmd=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(script)]
            flags={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
            result=subprocess.run(cmd+['-Disable'],capture_output=True,text=True,**flags);self.assertEqual(result.returncode,0)
            after=json.loads(p.read_text(encoding='utf-8-sig'));self.assertFalse(after['enabled']);self.assertTrue(after['comparison_enabled']);self.assertFalse(after['diagnostic_forecast'])
            result=subprocess.run(cmd,capture_output=True,text=True,**flags);self.assertNotEqual(result.returncode,0)
            self.assertFalse(json.loads(p.read_text(encoding='utf-8-sig'))['enabled'])


if __name__=='__main__':unittest.main()
