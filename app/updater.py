import hashlib, requests
from pathlib import Path
from .config import GITHUB_OWNER,GITHUB_REPO,GITHUB_BRANCH
class Updater:
    def __init__(self, log=lambda x:None): self.log=log
    @property
    def base(self): return f'https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_BRANCH}/updates'
    def manifest(self):
        r=requests.get(self.base+'/manifest.json',timeout=10); r.raise_for_status(); return r.json()
    def sha256(self,data): return hashlib.sha256(data).hexdigest()
    def newer(self,a,b): return tuple(map(int,a.split('.')))>tuple(map(int,b.split('.')))
    def download_scripts(self, m, dest):
        dest=Path(dest); dest.mkdir(parents=True,exist_ok=True)
        for f in m['files']:
            data=requests.get(self.base+'/'+f['name'],timeout=20).content
            if self.sha256(data).lower()!=f['sha256'].lower(): raise ValueError('Vérification SHA-256 échouée pour '+f['name'])
            (dest/f['name']).write_bytes(data)
