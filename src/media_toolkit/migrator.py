# src/media_toolkit/migrator.py
"""
Media Migration Module
"""

import click
import json
import shutil
import yaml
from pathlib import Path
from datetime import datetime
from typing import List
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .utils.hash import verify_file_hash

console = Console()


class MediaMigrator:
    """Handles migration of files to NAS"""
    
    def __init__(self, manifest_path: Path, target_root: Path):
        self.manifest_path = manifest_path
        self.target_root = Path(target_root)
        self.manifest = self._load_manifest()
        
        self.copied_count = 0
        self.copied_bytes = 0
        self.skipped_count = 0
        self.failed_count = 0
        self.errors: List[str] = []
    
    def _load_manifest(self) -> dict:
        """Load migration manifest"""
        with open(self.manifest_path) as f:
            return json.load(f)
    
    def _create_sidecar(self, media_file: dict, target_path: Path) -> None:
        """Create YAML sidecar metadata file"""
        sidecar_path = self.target_root / "Catalog" / "sidecars" / target_path.relative_to(self.target_root).with_suffix('.yaml')
        sidecar_path.parent.mkdir(parents=True, exist_ok=True)
        
        sidecar_data = {
            'id': media_file['hash'],
            'original_path': media_file['source_path'],
            'target_path': str(target_path),
            'device': media_file.get('device'),
            'file_type': media_file.get('file_type'),
            'size_bytes': media_file['size_bytes'],
            'creation_date': media_file.get('creation_date'),
            'migrated_at': datetime.now().isoformat(),
            'hash_blake3': media_file['hash'],
        }
        
        with open(sidecar_path, 'w') as f:
            yaml.dump(sidecar_data, f, default_flow_style=False)
    
    def migrate(self, batch_size: int = 50, dry_run: bool = False) -> None:
        """Execute migration"""
        
        files_to_migrate = [
            f for f in self.manifest['files']
            if not f.get('is_duplicate', False)
        ]
        
        total_files = len(files_to_migrate)
        total_size_gb = sum(f['size_bytes'] for f in files_to_migrate) / 1024**3
        
        console.print(f"\n[bold blue]Migration Plan:[/bold blue]")
        console.print(f"Files to copy: {total_files:,}")
        console.print(f"Total size: {total_size_gb:.2f} GB")
        
        if dry_run:
            console.print("\n[yellow]DRY RUN - No files will be copied[/yellow]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            
            task = progress.add_task("Migrating...", total=total_files)
            
            for media_file in files_to_migrate:
                source_path = Path(media_file['source_path'])
                target_path = self.target_root / media_file['target_path'].lstrip('/')
                
                try:
                    if dry_run:
                        progress.console.print(f"[dim]Would copy: {source_path.name}[/dim]")
                    else:
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        if target_path.exists():
                            if verify_file_hash(target_path, media_file['hash']):
                                self.skipped_count += 1
                                progress.update(task, advance=1)
                                continue
                        
                        shutil.copy2(source_path, target_path)
                        
                        if not verify_file_hash(target_path, media_file['hash']):
                            raise ValueError("Hash verification failed")
                        
                        self._create_sidecar(media_file, target_path)
                        self.copied_count += 1
                        self.copied_bytes += media_file['size_bytes']
                
                except Exception as e:
                    self.failed_count += 1
                    error_msg = f"Failed: {source_path}: {str(e)}"
                    self.errors.append(error_msg)
                    progress.console.print(f"[red]{error_msg}[/red]")
                
                progress.update(task, advance=1)
        
        console.print(f"\n[green]Copied: {self.copied_count:,}[/green]")
        console.print(f"[yellow]Skipped: {self.skipped_count:,}[/yellow]")
        console.print(f"[red]Failed: {self.failed_count:,}[/red]")


@click.command()
@click.option('--manifest', required=True, type=click.Path(exists=True))
@click.option('--target', required=True, type=click.Path())
@click.option('--batch-size', default=50, type=int)
@click.option('--dry-run', is_flag=True)
def main(manifest: str, target: str, batch_size: int, dry_run: bool):
    """Migrate files to NAS"""
    migrator = MediaMigrator(Path(manifest), Path(target))
    migrator.migrate(batch_size=batch_size, dry_run=dry_run)


if __name__ == '__main__':
    main()
