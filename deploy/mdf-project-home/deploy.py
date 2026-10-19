#!/usr/bin/env python3
"""Deploy a reversible MDF Asset Viewer project home without touching API/storage.
Precondition: test the static UI with browser-smoke.cjs and validate existing gallery patch anchors.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from patch_gallery import transform

PROJECT = Path(__file__).resolve().parent
STATIC = Path("/home/ubuntu/mdf-asset-viewer-private/characters/projects")
LIVE_JS = Path("/home/ubuntu/mdf-asset-viewer-private/asset-viewer-app.js")
BACKUPS = Path("/home/ubuntu/services/asset-viewer-live/backups")
FILES = ("index.html", "project-home.css", "project-home.js", "projects.json")
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def deploy():
    if STATIC.exists():
        raise RuntimeError("Destination already exists: refuse overwrite; inspect previous deployment")
    if not LIVE_JS.exists(): raise RuntimeError("Existing review script missing")
    live = LIVE_JS.read_text()
    patched = transform(live)  # verifies exact unique integration anchors BEFORE copying
    for name in FILES:
        if not (PROJECT/name).is_file(): raise RuntimeError("Missing source "+name)
    subprocess.run(["node","--check",str(PROJECT/"project-home.js")],check=True)
    with tempfile.TemporaryDirectory(dir=STATIC.parent,prefix=".project-home-stage-") as td:
        temp = Path(td)
        for name in FILES: shutil.copy2(PROJECT/name,temp/name)
        if sha(temp/"projects.json") != sha(PROJECT/"projects.json"):
            raise RuntimeError("staging mismatch")
        # Atomic publish of a new directory; only protected static paths are created.
        os.rename(temp, STATIC)
    try:
        from datetime import datetime,timezone
        bdir=BACKUPS / ("project-home-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
        bdir.mkdir(parents=True,exist_ok=False)
        shutil.copy2(LIVE_JS,bdir/"asset-viewer-app.js")
        fd, tmp=tempfile.mkstemp(prefix=".asset-viewer-app-",dir=LIVE_JS.parent)
        try:
            os.fchmod(fd,0o644)
            with os.fdopen(fd,"w") as out:
                out.write(patched);out.flush();os.fsync(out.fileno())
            os.replace(tmp,LIVE_JS)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
        if LIVE_JS.read_text()!=patched:raise RuntimeError("Patched JS verification failed")
        print("DEPLOY_PASS", "path="+str(STATIC),"js_sha256="+sha(LIVE_JS),"backup="+str(bdir/"asset-viewer-app.js"))
    except BaseException:
        # No modified JS means original entrypoint is intact; keep staged project files for diagnosis.
        print("DEPLOY_INCOMPLETE; inspect backup and live JS before retry",file=sys.stderr)
        raise

if __name__=="__main__":
    if "--apply" not in sys.argv: print("Check mode only; add --apply to publish. Source files:",FILES)
    else: deploy()
