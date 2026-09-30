"""Single-flight background refreshes with atomic, persistent last-good snapshots."""
import uuid
import hashlib
import json
import math
import pathlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor

class RefreshStore:
    def __init__(self, directory, ttl=60, version=None):
        self.directory = pathlib.Path(directory)
        self.ttl = ttl
        self.version = version
        self.lock = threading.Lock()
        self.jobs = {}
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='league-refresh')

    def _path(self, key):
        digest = hashlib.sha256(json.dumps(key).encode()).hexdigest()
        return self.directory / (digest + '.json')

    def _load(self, key):
        try:
            saved = json.loads(self._path(key).read_text())
            if (not isinstance(saved, dict) or not isinstance(saved.get('data'), dict)
                    or not isinstance(saved['data'].get('reports'), list) or not saved['data']['reports']
                    or not isinstance(saved.get('saved_at'), (float, int)) or not math.isfinite(saved['saved_at'])):
                return None
            return saved
        except (OSError, ValueError, TypeError, AttributeError):
            return None

    def _view(self, job):
        saved = job.get('saved')
        return {'status': job['status'], 'data': saved['data'] if saved else None,
                'error': job.get('error'), 'cached': bool(saved)}

    def read(self, key):
        with self.lock:
            job = self.jobs.get(key)
            return self._view(job) if job else self._view({'status': 'idle', 'saved': self._load(key)})

    def request(self, key, build, force=False):
        with self.lock:
            job = self.jobs.get(key)
            if job and job['status'] == 'refreshing':
                return self._view(job)
            saved = (job or {}).get('saved') or self._load(key)
            if saved and not force and (self.version is None or saved["data"].get("engine_version") == self.version) and time.time() - saved['saved_at'] < self.ttl:
                self.jobs[key] = {'status': 'ready', 'saved': saved}
                return self._view(self.jobs[key])
            job = {'status': 'refreshing', 'saved': saved, 'error': None}
            self.jobs[key] = job
            self.pool.submit(self._run, key, job, build)
            return self._view(job)

    def _run(self, key, job, build):
        try:
            data = build()
            if not isinstance(data, dict) or not data.get("reports"):
                raise ValueError("Refresh returned no reports")
            saved = {'saved_at': time.time(), 'data': data}
            # Commit only complete successful reports; preserve original source times.
            self.directory.mkdir(parents=True, exist_ok=True)
            target = self._path(key)
            temporary = target.with_name(target.name + "." + uuid.uuid4().hex + ".tmp")
            temporary.write_text(json.dumps(saved))
            temporary.replace(target)
            with self.lock:
                job.update(status='ready', saved=saved, error=None)
        except Exception:
            with self.lock:
                job.update(status='failed', error='Refresh unavailable. Your last successful report is retained; try again shortly.')
