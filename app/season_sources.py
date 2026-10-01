"""Shared, dated projection reads. Expired sources must refresh or fail closed."""
import hashlib
import json
import pathlib
import threading
import time
import uuid


class SourceCache:
    def __init__(self, directory, fetch, ttl=3600):
        self.directory=pathlib.Path(directory); self.fetch=fetch; self.ttl=ttl
        self.guard=threading.Lock(); self.locks={}; self.reads={}

    def __call__(self,url):
        with self.guard: lock=self.locks.setdefault(url,threading.Lock())
        with lock:
            path=self.directory/(hashlib.sha256(url.encode()).hexdigest()+'.json')
            try:
                saved=json.loads(path.read_text()); stamp=saved['read_at']
                if isinstance(stamp,(int,float)) and 0<=time.time()-stamp<self.ttl and isinstance(saved.get('data'),(list,dict)):
                    self.reads[url]=stamp; return saved['data']
            except (OSError,ValueError,KeyError,TypeError): pass
            value=self.fetch(url); stamp=time.time()
            if not isinstance(value,(list,dict)): raise ValueError('Source returned invalid data')
            self.directory.mkdir(parents=True,exist_ok=True)
            temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
            temp.write_text(json.dumps({'read_at':stamp,'data':value}));temp.replace(path)
            self.reads[url]=stamp;return value

    def read_at(self,url):
        return self.reads.get(url)
