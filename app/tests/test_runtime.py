import pathlib
import sys
import tempfile
import threading
import time
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from runtime import RefreshStore

class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = RefreshStore(self.temp.name)
        self.key = ('user', None)
        self.data = {'reports': [{'league': {'week': 4}}], 'freshness': {'roster_fetched_at': '2026-09-29T00:00:00Z'}}
    def tearDown(self):
        self.store.pool.shutdown(wait=True)
        self.temp.cleanup()
    def settled(self):
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            view = self.store.read(self.key)
            if view['status'] != 'refreshing': return view
            time.sleep(.005)
        self.fail('Background refresh did not finish')
    def test_single_flight_and_instant_return(self):
        gate = threading.Event()
        count = []
        def build():
            count.append(1); gate.wait(1); return self.data
        start = time.monotonic()
        self.assertEqual(self.store.request(self.key, build)['status'], 'refreshing')
        self.assertLess(time.monotonic() - start, .1)
        self.store.request(self.key, build, force=True)
        gate.set()
        self.assertEqual(self.settled()['data'], self.data)
        self.assertEqual(len(count), 1)
    def test_failure_retains_snapshot_and_original_date(self):
        self.store.request(self.key, lambda: self.data)
        self.settled()
        def broken(): raise TimeoutError()
        self.store.request(self.key, broken, force=True)
        result = self.settled()
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['data']['freshness'], self.data['freshness'])
    def test_restart_and_fresh_cache_avoid_new_work(self):
        self.store.request(self.key, lambda: self.data)
        self.settled()
        other = RefreshStore(self.temp.name)
        try:
            self.assertEqual(other.read(self.key)['data'], self.data)
            result = other.request(self.key, lambda: self.fail('Fresh cache recalculated'))
            self.assertEqual(result['status'], 'ready')
        finally: other.pool.shutdown(wait=True)
    def test_corrupt_cache_rebuilds_and_empty_response_keeps_good_data(self):
        self.store.directory.mkdir(exist_ok=True)
        self.store._path(self.key).write_text('bad json')
        self.store.request(self.key, lambda: self.data)
        self.settled()
        self.store.request(self.key, lambda: {'reports': []}, force=True)
        self.assertEqual(self.settled()['data'], self.data)

if __name__ == '__main__': unittest.main()

class VersionTests(unittest.TestCase):
    def test_fresh_prior_model_version_refreshes(self):
        with tempfile.TemporaryDirectory() as temp:
            store = RefreshStore(temp, version=2)
            key = ('user', None)
            data = {'reports':[{'league':{'week':4}}], 'engine_version':1}
            store.directory.mkdir(exist_ok=True)
            import json
            store._path(key).write_text(json.dumps({'data':data,'saved_at':time.time()}))
            gate = threading.Event()
            def new_report():
                gate.wait(1)
                return {**data,'engine_version':2}
            result = store.request(key,new_report)
            self.assertEqual(result['status'],'refreshing')
            self.assertEqual(result['data']['engine_version'],1)
            gate.set(); store.pool.shutdown(wait=True)
            self.assertEqual(store.read(key)['data']['engine_version'],2)
