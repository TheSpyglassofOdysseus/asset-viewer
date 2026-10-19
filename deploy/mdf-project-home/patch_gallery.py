#!/usr/bin/env python3
"""Minimal reversible integration of MDF Project Home with preexisting review client.
Intentionally leaves the original review engine, API and individual collection URLs intact.
"""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
from datetime import datetime, timezone

OLD_NAV = "  nav.innerHTML = navParts.join('');"
NEW_NAV = """  nav.innerHTML = '<a class="collection-link" href="/asset-viewer/">← Project home</a>' +
    '<details class="collection-fold"><summary>All source collections (' + state.collections.length + ')</summary>' +
    navParts.join('') + '</details>';"""
OLD_INIT = """(async () => {
  try {
    loadSavedViews();"""
NEW_INIT = """(async () => {
  // Project landing: only the bare root is redirected. Deep links, filters and reviews remain unchanged.
  if (location.pathname === '/asset-viewer/' && !location.search) {
    location.replace('/asset-viewer/characters/projects/');
    return;
  }
  try {
    loadSavedViews();"""
def digest(data): return hashlib.sha256(data).hexdigest()
def transform(source):
    if source.count(OLD_NAV) != 1 or source.count(OLD_INIT) != 1:
        raise ValueError("Integration anchors changed; refusing to overwrite")
    return source.replace(OLD_NAV, NEW_NAV).replace(OLD_INIT, NEW_INIT)

if __name__ == "__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",required=True,type=Path)
    ap.add_argument("--output",type=Path)
    ap.add_argument("--apply",action="store_true")
    args=ap.parse_args()
    original=args.source.read_text()
    updated=transform(original)
    print("source_sha256="+digest(original.encode()))
    print("patched_sha256="+digest(updated.encode()))
    if args.apply:
        backup_dir=Path("/home/ubuntu/services/asset-viewer-live/backups/project-home-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
        backup_dir.mkdir(parents=True,exist_ok=False)
        shutil.copy2(args.source,backup_dir/"asset-viewer-app.js")
        fd,tmp=tempfile.mkstemp(prefix="asset-viewer-app.",dir=str(args.source.parent))
        try:
            os.fchmod(fd,0o644)
            with os.fdopen(fd,'w') as f:
                f.write(updated);f.flush();os.fsync(f.fileno())
            os.replace(tmp,args.source)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
        print("backup="+str(backup_dir/"asset-viewer-app.js"))
        print("deployed_sha256="+digest(args.source.read_bytes()))
    elif args.output:
        args.output.write_text(updated)
        print("preview="+str(args.output))
    else:
        print("dry_run=PASS")
