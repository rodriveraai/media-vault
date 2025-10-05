# ============================================================================
# FILE: src/media_toolkit/models.py
# ============================================================================
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List

@dataclass
class MediaFile:
    """Represents a media file with metadata"""
    source_path: Path
    size_bytes: int
    hash: str  # BLAKE3 hash
    creation_date: Optional[datetime] = None
    device: Optional[str] = None
    target_path: Optional[Path] = None
    file_type: str = "unknown"  # video, audio, image, metadata
    is_duplicate: bool = False
    duplicate_group_id: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    
    @property
    def size_mb(self) -> float:
        return self.size_bytes / 1024 / 1024
    
    @property
    def size_gb(self) -> float:
        return self.size_bytes / 1024 / 1024 / 1024

@dataclass
class MigrationManifest:
    """Complete migration plan"""
    source_root: Path
    target_root: Path
    total_files: int
    total_size_bytes: int
    files: List[MediaFile]
    duplicate_groups: dict
    created_at: datetime
    
    @property
    def total_size_gb(self) -> float:
        return self.total_size_bytes / 1024 / 1024 / 1024