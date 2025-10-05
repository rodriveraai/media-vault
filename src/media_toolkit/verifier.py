# src/media_toolkit/verifier.py
"""
Migration Verifier
"""

import click
import json
from pathlib import Path
from typing import List
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .utils.hash import verify_file_hash

console = Console()


class MigrationVerifier:
    """Verifies migration completeness"""
    
    def __init__(self, manifest_path: Path, target_root: Path):
        self.manifest_path = manifest_path
        self.target_root = Path(target_root)
        self.manifest = self._load_manifest()
        
        self.verified_count = 0
        self.missing_count = 0
        self.corrupted_count = 0
        self.errors: List[str] = []
    
    def _load_manifest(self) -> dict:
        """Load migration manifest"""
        with open(self.manifest_path) as f:
            return json.load(f)
    
    def verify(self) -> None:
        """Verify all files copied correctly"""
        
        files_to_verify = [
            f for f in self.manifest['files']
            if not f.get('is_duplicate', False)
        ]
        
        console.print(f"\n[bold blue]Verifying {len(files_to_verify):,} files...[/bold blue]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            
            task = progress.add_task("Verifying...", total=len(files_to_verify))
            
            for media_file in files_to_verify:
                target_path = self.target_root / media_file['target_path'].lstrip('/')
                
                try:
                    if not target_path.exists():
                        self.missing_count += 1
                        error = f"Missing: {target_path}"
                        self.errors.append(error)
                        progress.update(task, advance=1)
                        continue
                    
                    if not verify_file_hash(target_path, media_file['hash']):
                        self.corrupted_count += 1
                        error = f"Corrupted: {target_path}"
                        self.errors.append(error)
                        progress.update(task, advance=1)
                        continue
                    
                    self.verified_count += 1
                
                except Exception as e:
                    error = f"Error: {target_path}: {str(e)}"
                    self.errors.append(error)
                
                progress.update(task, advance=1)
        
        console.print(f"\n[green]Verified: {self.verified_count:,}[/green]")
        console.print(f"[red]Missing: {self.missing_count:,}[/red]")
        console.print(f"[red]Corrupted: {self.corrupted_count:,}[/red]")
        
        if self.missing_count == 0 and self.corrupted_count == 0:
            console.print("\n[bold green]All verified! Safe to clean SSD.[/bold green]")
        else:
            console.print("\n[bold red]ERRORS - Do not delete source![/bold red]")


@click.command()
@click.option('--manifest', required=True, type=click.Path(exists=True))
@click.option('--target', required=True, type=click.Path(exists=True))
def main(manifest: str, target: str):
    """Verify migration"""
    verifier = MigrationVerifier(Path(manifest), Path(target))
    verifier.verify()


if __name__ == '__main__':
    main()
