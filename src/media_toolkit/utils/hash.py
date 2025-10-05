# ============================================================================
# FILE: src/media_toolkit/utils/hash.py
# ============================================================================
import blake3
from pathlib import Path
from typing import Optional

def compute_file_hash(filepath: Path, chunk_size: int = 65536) -> str:
    """
    Compute BLAKE3 hash of a file.
    
    Args:
        filepath: Path to file
        chunk_size: Read chunk size (default 64KB)
    
    Returns:
        Hexadecimal hash string
    """
    hasher = blake3.blake3()
    
    with open(filepath, 'rb') as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    
    return hasher.hexdigest()

def verify_file_hash(filepath: Path, expected_hash: str) -> bool:
    """Verify file matches expected hash"""
    actual_hash = compute_file_hash(filepath)
    return actual_hash == expected_hash