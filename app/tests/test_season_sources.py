import concurrent.futures
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from season_sources import SourceCache
from season_rosters import context


class SourceTests(unittest.TestCase):
    def test_shared_read_preserves_date_and_expires_without_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            calls=[]
            def fetch(url):
                calls.append(url)
                if len(calls)>1: raise TimeoutError('fixture outage')
                return [{'stats': {'rec': 2}}]
            source=SourceCache(folder,fetch,ttl=10)
            with patch('season_sources.time.time',return_value=100):
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                    results=list(pool.map(source,['fixture']*4))
                self.assertEqual(len(calls),1)
                self.assertEqual(results[0],results[3])
            with patch('season_sources.time.time',return_value=105):
                source('fixture')
                self.assertEqual(source.read_at('fixture'),100)
            with patch('season_sources.time.time',return_value=111):
                with self.assertRaises(TimeoutError): source('fixture')
            saved=json.loads(next(pathlib.Path(folder).glob('*.json')).read_text())
            self.assertEqual(saved['read_at'],100)
            self.assertEqual(saved['data'],results[0])
            source.fetch=lambda url: [{'stats': {'rec':3}}]
            with patch('season_sources.time.time',return_value=112):
                self.assertEqual(source('fixture')[0]['stats']['rec'],3)
                self.assertEqual(source.read_at('fixture'),112)

    def test_corrupt_or_wrong_shape_cache_is_rebuilt(self):
        with tempfile.TemporaryDirectory() as folder:
            source=SourceCache(folder,lambda url: {'fresh':True})
            source('fixture')
            path=next(pathlib.Path(folder).glob('*.json'))
            path.write_text('broken')
            self.assertEqual(source('fixture'),{'fresh':True})
            saved=json.loads(path.read_text());saved['data']='invalid';path.write_text(json.dumps(saved))
            self.assertEqual(source('fixture'),{'fresh':True})

    def test_incomplete_and_duplicate_ownership_fail_closed(self):
        league={'season':'2026','sport':'nfl','name':'Fixture','total_rosters':2,
                'scoring_settings':{'rec':.5},'roster_positions':['RB','BN']}
        rosters=[{'owner_id':'user','players':['1']},{'owner_id':'other','players':['2']}]
        def fetch(url):
            if '/user/' in url: return {'user_id':'user'}
            return rosters if url.endswith('/rosters') else league
        self.assertEqual(context(fetch,'fixture','1',2026)['owned'],{'1'})
        rosters[1]['players']=['1']
        with self.assertRaisesRegex(ValueError,'Duplicate'): context(fetch,'fixture','1',2026)
        rosters.pop()
        with self.assertRaisesRegex(ValueError,'incomplete'): context(fetch,'fixture','1',2026)


if __name__ == '__main__': unittest.main()
