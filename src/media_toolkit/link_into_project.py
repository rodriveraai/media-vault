# src/media_toolkit/link_into_project.py
from __future__ import annotations
import os, yaml, click
from pathlib import Path
from datetime import datetime

def safe_symlink(target: Path, link: Path):
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.exists() or link.is_symlink():
        try: link.unlink()
        except: pass
    link.symlink_to(target)

@click.command()
@click.option("--root", required=True, type=click.Path(exists=True), help="NAS media root (/Volumes/RodNAS/Media)")
@click.option("--project", required=True, help="project name, e.g. billion_ep-024")
@click.option("--shoot", required=True, help="e.g. 2025-10-05_london_office")
@click.option("--date", required=True, help="YYYY-MM-DD")
@click.option("--device", multiple=True, help="CAM device(s), e.g. fx3,fx30,zv-e10,... (repeat flag)")
def main(root: str, project: str, shoot: str, date: str, device: list[str]):
    """
    Create symlink aliases under Projects/... by scanning Originals for the date/devices.
    """
    root_p = Path(root)
    year = date.split("-")[0]
    proj_root = root_p / "Projects" / year / f"{date}_{project}" / "02_shoots" / shoot / "VIDEO"

    cams = device or ["fx3","fx30","zv-e10","osmo-pocket-3","riverside"]
    for cam in cams:
        cam_src_dir = root_p / "Originals" / f"CAM_{cam}" / year / date
        cam_dst_dir = proj_root / f"CAM_{cam}"
        if not cam_src_dir.exists():
            continue
        for f in cam_src_dir.iterdir():
            if f.is_file() and f.suffix.lower() in (".mp4",".mov",".mxf",".m4v"):
                alias = f"{date}_{project}_cam-{cam}_{f.name}"
                safe_symlink(f, cam_dst_dir / alias)

    click.echo(f"Symlinks created under: {proj_root}")

if __name__ == "__main__":
    main()
