# src/media_toolkit/catalog.py
from __future__ import annotations
import json, sqlite3, sys
from pathlib import Path
from datetime import datetime
from typing import Optional
import click
import yaml

SCHEMA = """
CREATE TABLE IF NOT EXISTS clips(
  id TEXT PRIMARY KEY,                -- blake3:<hex> or <hex>
  original_path TEXT NOT NULL,
  target_path TEXT NOT NULL,
  device TEXT,
  file_type TEXT,
  size_bytes INTEGER,
  creation_date TEXT,                 -- ISO8601
  migrated_at TEXT,                   -- ISO8601
  alias TEXT,                         -- future: project alias name
  project TEXT,                       -- future
  shoot TEXT,                         -- future
  track TEXT,                         -- VIDEO/AUDIO (future)
  width INTEGER, height INTEGER, fps REAL, codec TEXT  -- optional future enrich
);
CREATE INDEX IF NOT EXISTS idx_device ON clips(device);
CREATE INDEX IF NOT EXISTS idx_created ON clips(creation_date);
"""

def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    con.executescript(SCHEMA)
    return con

def upsert_sidecar(con: sqlite3.Connection, sidecar_path: Path, root: Path) -> None:
    with sidecar_path.open("r") as f:
        sc = yaml.safe_load(f)

    clip_id = sc.get("id") or sc.get("hash_blake3")
    # normalize id to "blake3:<hex>"
    if clip_id and not str(clip_id).startswith("blake3:"):
        clip_id = f"blake3:{clip_id}"

    # resolve stored paths to absolute-on-NAS if they are relative
    original_path = sc.get("original_path")
    target_path   = sc.get("target_path")
    if isinstance(original_path, str) and original_path.startswith("/"):
        op = original_path
    else:
        op = str((root / str(original_path).lstrip("/")).resolve())

    if isinstance(target_path, str) and target_path.startswith("/"):
        tp = target_path
    else:
        tp = str((root / str(target_path).lstrip("/")).resolve())

    con.execute(
        """
        INSERT INTO clips(id, original_path, target_path, device, file_type, size_bytes,
                          creation_date, migrated_at, alias, project, shoot, track, width, height, fps, codec)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
          original_path=excluded.original_path,
          target_path=excluded.target_path,
          device=excluded.device,
          file_type=excluded.file_type,
          size_bytes=excluded.size_bytes,
          creation_date=excluded.creation_date,
          migrated_at=excluded.migrated_at,
          alias=excluded.alias,
          project=excluded.project,
          shoot=excluded.shoot,
          track=excluded.track,
          width=excluded.width,
          height=excluded.height,
          fps=excluded.fps,
          codec=excluded.codec
        """,
        (
            clip_id,
            op,
            tp,
            sc.get("device"),
            sc.get("file_type"),
            sc.get("size_bytes"),
            sc.get("creation_date"),
            sc.get("migrated_at"),
            sc.get("alias"),
            sc.get("project"),
            sc.get("shoot"),
            sc.get("track"),
            sc.get("width"),
            sc.get("height"),
            sc.get("fps"),
            sc.get("codec"),
        ),
    )

@click.group()
def cli():
    """Catalog utilities"""
    pass

@cli.command("index-sidecars")
@click.option("--catalog", required=True, type=click.Path())
@click.option("--root", required=True, type=click.Path(exists=True), help="NAS media root (e.g. /Volumes/RodNAS/Media)")
@click.option("--sidecars-dir", default=None, type=click.Path(), help="Override sidecars dir (defaults to <root>/Catalog/sidecars)")
def index_sidecars(catalog: str, root: str, sidecars_dir: Optional[str]):
    """Index all YAML sidecars into SQLite catalog."""
    db_path = Path(catalog)
    root_p = Path(root)
    sidecars = Path(sidecars_dir) if sidecars_dir else (root_p / "Catalog" / "sidecars")
    con = _connect(db_path)
    count = 0
    try:
        for yml in sidecars.rglob("*.yaml"):
            upsert_sidecar(con, yml, root_p)
            count += 1
        con.commit()
        click.echo(f"Indexed {count} sidecars into {db_path}")
    finally:
        con.close()

if __name__ == "__main__":
    cli()
