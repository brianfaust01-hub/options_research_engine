import sys,unittest
from pathlib import Path
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'src'))
from schwab import market_token_manager as tokens,market_data_client as client


class CachedAuthorizationTests(unittest.TestCase):
    def test_cached_quote_authorization_never_refreshes_or_writes(self):
        with patch.object(tokens,'_load_tokens',return_value={'access_token':'fixture-only'}),patch.object(tokens,'_access_token_is_valid',return_value=True),patch.object(tokens,'_refresh_access_token') as refresh,patch.object(tokens,'_save_tokens') as save:
            self.assertEqual(tokens.get_cached_access_token(),'fixture-only')
            refresh.assert_not_called();save.assert_not_called()
        with patch.object(tokens,'_load_tokens',return_value={}),patch.object(tokens,'_access_token_is_valid',return_value=False),patch.object(tokens,'_refresh_access_token') as refresh:
            with self.assertRaises(RuntimeError):tokens.get_cached_access_token()
            refresh.assert_not_called()

    def test_quote_adapter_uses_cached_path_only_when_requested(self):
        response=Mock();response.json.return_value={}
        with patch.object(client,'get_cached_access_token',return_value='fixture-only') as cached,patch.object(client,'get_access_token') as regular,patch.object(client.requests,'get',return_value=response):
            self.assertEqual(client.get_option_quotes(['EXACT CONTRACT'],cached_auth_only=True),{})
            cached.assert_called_once();regular.assert_not_called()


if __name__=='__main__':unittest.main()
