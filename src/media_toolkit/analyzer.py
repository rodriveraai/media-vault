# src/media_toolkit/analyzer.py
"""
Media Archive Analyzer

Scans existing media archive, extracts metadata, detects duplicates,
and generates migration plan.
"""

import click
import json
import yaml
import csv
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from itertools import chain

from .models import MediaFile, MigrationManifest
from .utils.hash import compute_file_hash
from .utils.ffprobe import extract_video_metadata

console = Console()


class MediaAnalyzer:
    """Analyzes media archive and creates migration plan"""
    
    def __init__(self, source_root: Path, config_path: Path):
        self.source_root = Path(source_root)
        self.config = self._load_config(config_path)
        
        # Storage for analysis results
        self.files: List[MediaFile] = []
        self.hash_index: Dict[str, List[MediaFile]] = defaultdict(list)
        self.total_bytes = 0
        self.errors: List[str] = []
        
    def _load_config(self, config_path: Path) -> dict:
        """Load device mappings and configuration"""
        with open(config_path) as f:
            return yaml.safe_load(f)
    
    def _should_exclude(self, path: Path) -> bool:
        """Check if file/folder should be excluded"""
        # interpret patterns against logical path (post-strip)
        logical_rel = self._logical_relpath(path) if path.is_absolute() else path
        path_str = str(logical_rel)
        
        for pattern in self.config.get('exclude', []):
            if pattern.startswith('*'):
                # Extension match
                if path.name.endswith(pattern[1:]):
                    return True
            elif '*' in pattern:
                # Wildcard pattern (simplified matching)
                import fnmatch
                if fnmatch.fnmatch(path_str, f"*{pattern}*"):
                    return True
            else:
                # Exact match
                if pattern in path_str:
                    return True
        
        return False
    
    def _extract_date_from_filename(self, filename: str, pattern: str) -> Optional[datetime]:
        """Extract date from filename using regex pattern"""
        import re
        match = re.search(pattern, filename)
        if match:
            date_str = match.group(1)
            try:
                return datetime.strptime(date_str, "%Y%m%d")
            except ValueError:
                pass
        return None
    
    def _logical_relpath(self, filepath: Path) -> Path:
        """
        Return a 'logical' project-relative path by stripping any configured
        source_roots prefixes (e.g., '00_raw_sources/') if present.
        This allows device mappings like 'sony-fx-3' to match even when the
        physical path is '00_raw_sources/sony-fx-3/...'
        """
        rel = filepath.relative_to(self.source_root)
        parts = rel.parts
        source_roots = self.config.get("source_roots", [])
        if parts and source_roots:
            # If first segment matches any configured source root, drop it
            if parts[0] in source_roots:
                return Path(*parts[1:]) if len(parts) > 1 else Path(".")
        return rel

    def _determine_device(self, filepath: Path) -> Optional[str]:
        """Determine device name from (logical) file path"""
        logical_rel = self._logical_relpath(filepath)
        path_str = str(logical_rel)

        # Check device mappings - longest key first for specificity
        sorted_devices = sorted(self.config['devices'].items(), key=lambda x: len(x[0]), reverse=True)
        for source_folder, device_name in sorted_devices:
            # we match at folder boundary: "<key>/" or exact "<key>"
            if path_str == source_folder or path_str.startswith(source_folder + '/'):
                return device_name

        # Riverside fallback (unchanged)
        if self.config.get('riverside', {}).get('enabled', False):
            for pattern in self.config['riverside'].get('source_patterns', []):
                import fnmatch
                if fnmatch.fnmatch(path_str, pattern):
                    return self.config['riverside']['device_name']

        # audio-tracks fallback (unchanged)
        if path_str.startswith('audio-tracks'):
            pattern = self.config.get('audio_tracks', {}).get('filename_pattern')
            if pattern:
                return self.config['devices'].get('dji-mic-2', 'AUDIO_dji-mic-2')

        return None

    def _determine_target_path(self, media_file: MediaFile) -> Path:
        """Determine target path for a media file"""
        logical_rel = self._logical_relpath(media_file.source_path)
        path_str = str(logical_rel)

        # Project-preserve rules against logical path
        for project in self.config.get('projects', []):
            if path_str.startswith(project['source_path']):
                if project.get('preserve_structure', False):
                    internal_path = Path(path_str).relative_to(project['source_path'])
                    return Path(project['target_path']) / internal_path
                else:
                    return Path(project['target_path']) / media_file.source_path.name

        # audio-tracks rule (unchanged, but using logical path)
        if path_str.startswith('audio-tracks'):
            audio_config = self.config.get('audio_tracks', {})
            if audio_config.get('extract_date_from_filename'):
                pattern = audio_config.get('filename_pattern')
                date = self._extract_date_from_filename(media_file.source_path.name, pattern)
                if date:
                    target_base = Path(audio_config['target_base'])
                    ymd = f"{date.year}/{date.year}-{date.month:02d}-{date.day:02d}"
                    return target_base / ymd / media_file.source_path.name

        # Standard device-based organization
        if media_file.device and media_file.creation_date:
            device_path = Path(f"/Originals/{media_file.device}")
            year = media_file.creation_date.year
            date_str = media_file.creation_date.strftime("%Y-%m-%d")
            return device_path / str(year) / date_str / media_file.source_path.name

        # Fallback
        return Path(f"/Originals/_unknown/{media_file.source_path.name}")
    
    def _get_file_type(self, filepath: Path) -> str:
        """Determine file type from extension"""
        ext = filepath.suffix.lower()
        
        for file_type, config in self.config.get('file_types', {}).items():
            if ext in [e.lower() for e in config.get('extensions', [])]:
                return file_type
        
        return 'unknown'
    
    def _process_file(self, filepath: Path) -> Optional[MediaFile]:
        """Process a single media file"""
        try:
            # Get file stats
            stat = filepath.stat()
            size_bytes = stat.st_size
            
            # Skip very small files (likely metadata or corrupted)
            min_size = self.config.get('duplicates', {}).get('min_size_bytes', 1048576)
            if size_bytes < min_size:
                return None
            
            # Compute hash
            file_hash = compute_file_hash(filepath)
            
            # Extract creation date
            creation_date = None
            file_type = self._get_file_type(filepath)
            
            if file_type == 'video':
                metadata = extract_video_metadata(filepath)
                creation_date = metadata.get('creation_date')
            
            # Fallback to filesystem date
            if not creation_date:
                creation_date = datetime.fromtimestamp(
                    stat.st_birthtime if hasattr(stat, 'st_birthtime') else stat.st_mtime
                )
            
            # Determine device
            device = self._determine_device(filepath)
            
            # Create MediaFile object
            media_file = MediaFile(
                source_path=filepath,
                size_bytes=size_bytes,
                hash=file_hash,
                creation_date=creation_date,
                device=device,
                file_type=file_type,
            )
            
            # Determine target path
            media_file.target_path = self._determine_target_path(media_file)
            
            return media_file
            
        except Exception as e:
            self.errors.append(f"Error processing {filepath}: {str(e)}")
            return None
    
    def scan(self, dry_run: bool = False) -> None:
        """Scan source directory and build file list"""
        console.print(f"\n[bold blue]Scanning:[/bold blue] {self.source_root}")
        
        if dry_run:
            console.print("[yellow]DRY RUN - No hashes will be computed[/yellow]")
        
        # Collect all media files
        all_files = []
        for root, dirs, files in self.source_root.walk():
            # Filter out excluded directories
            dirs[:] = [d for d in dirs if not self._should_exclude(root / d)]
            
            for filename in files:
                filepath = root / filename
                
                # Skip excluded files
                if self._should_exclude(filepath):
                    continue
                
                # Only process media files
                file_type = self._get_file_type(filepath)
                if file_type in ['video', 'audio', 'image']:
                    all_files.append(filepath)
        
        console.print(f"Found [bold]{len(all_files)}[/bold] media files to process")

        # After collecting all_files, do a quick sanity report:
        logical_top_levels = set()
        for p in all_files:
            lr = self._logical_relpath(p)
            if lr.parts:
                logical_top_levels.add(lr.parts[0])
        unknown = sorted(x for x in logical_top_levels if x not in self.config.get('devices', {}))
        if unknown:
            console.print(f"[yellow]Note:[/yellow] Unmapped top-level folders under source_roots: {', '.join(unknown)}")
        
        # Process files with progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            
            task = progress.add_task(
                "Processing files...", 
                total=len(all_files)
            )
            
            for filepath in all_files:
                if dry_run:
                    # Quick scan without hashing
                    stat = filepath.stat()
                    media_file = MediaFile(
                        source_path=filepath,
                        size_bytes=stat.st_size,
                        hash="DRY_RUN",
                        creation_date=datetime.now(),
                        device=self._determine_device(filepath),
                        file_type=self._get_file_type(filepath),
                    )
                    media_file.target_path = self._determine_target_path(media_file)
                else:
                    media_file = self._process_file(filepath)
                
                if media_file:
                    self.files.append(media_file)
                    self.total_bytes += media_file.size_bytes
                    
                    if not dry_run:
                        self.hash_index[media_file.hash].append(media_file)
                
                progress.update(task, advance=1)
        
        console.print(f"[green]✓[/green] Processed {len(self.files)} files")
        console.print(f"[green]✓[/green] Total size: {self.total_bytes / 1024**3:.2f} GB")
    
    def detect_duplicates(self) -> Dict[str, List[MediaFile]]:
        """Identify duplicate files and mark them"""
        console.print("\n[bold blue]Detecting duplicates...[/bold blue]")
        
        duplicate_groups = {}
        total_duplicates = 0
        space_saved_bytes = 0
        
        for file_hash, file_list in self.hash_index.items():
            if len(file_list) > 1:
                # Multiple files with same hash = duplicates
                duplicate_groups[file_hash] = file_list
                
                # Determine primary file based on priority
                primary = self._select_primary_duplicate(file_list)
                
                for media_file in file_list:
                    media_file.is_duplicate = True
                    media_file.duplicate_group_id = file_hash
                    
                    if media_file is not primary:
                        space_saved_bytes += media_file.size_bytes
                        total_duplicates += 1
        
        console.print(f"[yellow]Found {len(duplicate_groups)} duplicate groups[/yellow]")
        console.print(f"[yellow]Total duplicate files: {total_duplicates}[/yellow]")
        console.print(f"[green]Space to be saved: {space_saved_bytes / 1024**3:.2f} GB[/green]")
        
        return duplicate_groups
    
    def _select_primary_duplicate(self, duplicates: List[MediaFile]) -> MediaFile:
        """Select which duplicate to keep as primary"""
        priority_patterns = self.config.get('duplicates', {}).get('priority', [])
        
        # Score each file based on path priority
        scored = []
        for media_file in duplicates:
            score = 0
            path_str = str(media_file.target_path)
            
            for i, pattern in enumerate(priority_patterns):
                import fnmatch
                if fnmatch.fnmatch(path_str, pattern):
                    score = len(priority_patterns) - i
                    break
            
            scored.append((score, media_file.creation_date, media_file))
        
        # Sort by score (desc), then date (asc)
        scored.sort(key=lambda x: (-x[0], x[1] or datetime.max))
        
        return scored[0][2]
    
    def generate_manifest(self, output_dir: Path) -> MigrationManifest:
        """Generate migration manifest"""
        console.print("\n[bold blue]Generating migration manifest...[/bold blue]")
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create manifest
        manifest = MigrationManifest(
            source_root=self.source_root,
            target_root=Path("/Volumes/RodNAS/Media"),
            total_files=len(self.files),
            total_size_bytes=self.total_bytes,
            files=self.files,
            duplicate_groups=self.hash_index,
            created_at=datetime.now(),
        )
        
        # Save as JSON using Pydantic serialization
        manifest_path = output_dir / "migration_manifest.json"
        manifest_dict = manifest.model_dump(mode='json')
        # Convert Path objects to strings for JSON
        manifest_dict['source_root'] = str(manifest.source_root)
        manifest_dict['target_root'] = str(manifest.target_root)
        manifest_dict['created_at'] = manifest.created_at.isoformat()
        manifest_dict['total_size_gb'] = manifest.total_size_gb
        
        for file_data in manifest_dict['files']:
            file_data['source_path'] = str(file_data['source_path'])
            file_data['target_path'] = str(file_data['target_path']) if file_data['target_path'] else None
            file_data['creation_date'] = file_data['creation_date'] if file_data.get('creation_date') else None
            # Add computed properties
            size_bytes = file_data['size_bytes']
            file_data['size_mb'] = size_bytes / 1024 / 1024
        
        with open(manifest_path, 'w') as f:
            json.dump(manifest_dict, f, indent=2, default=str)
        
        console.print(f"[green]✓[/green] Saved manifest: {manifest_path}")
        
        # Save duplicates report
        self._save_duplicates_report(output_dir)
        
        # Save summary
        self._save_summary(output_dir, manifest)
        
        return manifest
    
    def _save_duplicates_report(self, output_dir: Path) -> None:
        """Save detailed duplicates report as CSV"""
        duplicates_path = output_dir / "duplicates_report.csv"
        
        with open(duplicates_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'hash', 'primary_path', 'duplicate_paths', 
                'count', 'size_mb', 'size_saved_mb'
            ])
            
            for file_hash, file_list in self.hash_index.items():
                if len(file_list) > 1:
                    primary = self._select_primary_duplicate(file_list)
                    duplicates = [f for f in file_list if f is not primary]
                    
                    duplicate_paths = '; '.join(str(f.source_path) for f in duplicates)
                    size_saved = sum(f.size_mb for f in duplicates)
                    
                    writer.writerow([
                        file_hash,
                        str(primary.source_path),
                        duplicate_paths,
                        len(file_list),
                        primary.size_mb,
                        size_saved,
                    ])
        
        console.print(f"[green]✓[/green] Saved duplicates report: {duplicates_path}")
    
    def _save_summary(self, output_dir: Path, manifest: MigrationManifest) -> None:
        """Save human-readable summary"""
        summary_path = output_dir / "analysis_summary.txt"
        
        # Calculate statistics
        by_device = defaultdict(lambda: {'count': 0, 'size': 0})
        by_type = defaultdict(lambda: {'count': 0, 'size': 0})
        
        for f in self.files:
            if f.device:
                by_device[f.device]['count'] += 1
                by_device[f.device]['size'] += f.size_bytes
            
            by_type[f.file_type]['count'] += 1
            by_type[f.file_type]['size'] += f.size_bytes
        
        duplicates_count = sum(1 for f in self.files if f.is_duplicate)
        primary_count = len([files for files in self.hash_index.values() if len(files) > 1])
        
        with open(summary_path, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("MEDIA ARCHIVE ANALYSIS SUMMARY\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Source: {manifest.source_root}\n")
            f.write(f"Target: {manifest.target_root}\n\n")
            
            f.write("-" * 80 + "\n")
            f.write("OVERVIEW\n")
            f.write("-" * 80 + "\n")
            f.write(f"Total Files: {manifest.total_files:,}\n")
            f.write(f"Total Size: {manifest.total_size_gb:.2f} GB\n")
            f.write(f"Duplicate Groups: {primary_count}\n")
            f.write(f"Duplicate Files: {duplicates_count}\n\n")
            
            f.write("-" * 80 + "\n")
            f.write("BY DEVICE\n")
            f.write("-" * 80 + "\n")
            for device, stats in sorted(by_device.items()):
                f.write(f"{device:30} {stats['count']:6,} files  {stats['size']/1024**3:8.2f} GB\n")
            f.write("\n")
            
            f.write("-" * 80 + "\n")
            f.write("BY FILE TYPE\n")
            f.write("-" * 80 + "\n")
            for file_type, stats in sorted(by_type.items()):
                f.write(f"{file_type:30} {stats['count']:6,} files  {stats['size']/1024**3:8.2f} GB\n")
            f.write("\n")
            
            if self.errors:
                f.write("-" * 80 + "\n")
                f.write(f"ERRORS ({len(self.errors)})\n")
                f.write("-" * 80 + "\n")
                for error in self.errors[:50]:  # First 50 errors
                    f.write(f"  {error}\n")
                if len(self.errors) > 50:
                    f.write(f"  ... and {len(self.errors) - 50} more\n")
        
        console.print(f"[green]✓[/green] Saved summary: {summary_path}")


@click.command()
@click.option('--source', required=True, type=click.Path(exists=True), help='Source volume path')
@click.option('--output', required=True, type=click.Path(), help='Output directory for results')
@click.option('--config', type=click.Path(exists=True), default='config/device_mappings.yaml', help='Config file')
@click.option('--dry-run', is_flag=True, help='Dry run (no hash computation)')
def main(source: str, output: str, config: str, dry_run: bool):
    """Analyze media archive and create migration plan"""
    
    console.print("\n[bold cyan]Media Archive Analyzer[/bold cyan]")
    console.print(f"Version 0.1.0\n")
    
    analyzer = MediaAnalyzer(
        source_root=Path(source),
        config_path=Path(config),
    )
    
    # Scan files
    analyzer.scan(dry_run=dry_run)
    
    # Detect duplicates (skip in dry-run)
    if not dry_run:
        analyzer.detect_duplicates()
    
    # Generate manifest
    analyzer.generate_manifest(Path(output))
    
    console.print("\n[bold green]✓ Analysis complete![/bold green]")
    console.print(f"\nResults saved to: {output}/")
    console.print("\nNext steps:")
    console.print("  1. Review migration_manifest.json")
    console.print("  2. Check duplicates_report.csv")
    console.print("  3. When NAS arrives: make migrate")


if __name__ == '__main__':
    main()