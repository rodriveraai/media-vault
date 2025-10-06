# src/media_toolkit/models.py
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from pathlib import Path
from typing import Optional

class MediaFile(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    source_path: Path
    size_bytes: int = Field(ge=0)  # Changed from gt=0 to ge=0 (allow zero bytes)
    hash: str = Field(min_length=1, max_length=128)
    creation_date: Optional[datetime] = None
    device: Optional[str] = None
    target_path: Optional[Path] = None
    file_type: str = "unknown"
    is_duplicate: bool = False
    duplicate_group_id: Optional[str] = None
    errors: list[str] = Field(default_factory=list)
    
    @property
    def size_mb(self) -> float:
        return self.size_bytes / 1024 / 1024
    
    @property
    def size_gb(self) -> float:
        return self.size_bytes / 1024 / 1024 / 1024

class MigrationManifest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    source_root: Path
    target_root: Path
    total_files: int = Field(ge=0)
    total_size_bytes: int = Field(ge=0)
    files: list[MediaFile]
    duplicate_groups: dict
    created_at: datetime
    
    @property
    def total_size_gb(self) -> float:
        return self.total_size_bytes / 1024 / 1024 / 1024
