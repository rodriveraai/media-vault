# ============================================================================
# FILE: src/media_toolkit/utils/ffprobe.py
# ============================================================================
import subprocess
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

def extract_video_metadata(filepath: Path) -> Dict[str, Any]:
    """
    Extract metadata from video file using ffprobe.
    Falls back to filesystem metadata if ffprobe unavailable.
    """
    metadata = {
        'duration': None,
        'width': None,
        'height': None,
        'codec': None,
        'fps': None,
        'creation_date': None,
    }
    
    try:
        # Try ffprobe first
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            str(filepath)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            data = json.loads(result.stdout)
            
            # Extract creation time
            if 'format' in data and 'tags' in data['format']:
                tags = data['format']['tags']
                for key in ['creation_time', 'date', 'DATE']:
                    if key in tags:
                        try:
                            metadata['creation_date'] = datetime.fromisoformat(
                                tags[key].replace('Z', '+00:00')
                            )
                            break
                        except:
                            pass
            
            # Extract video stream info
            if 'streams' in data:
                for stream in data['streams']:
                    if stream.get('codec_type') == 'video':
                        metadata['width'] = stream.get('width')
                        metadata['height'] = stream.get('height')
                        metadata['codec'] = stream.get('codec_name')
                        
                        # Calculate FPS
                        if 'r_frame_rate' in stream:
                            num, den = map(int, stream['r_frame_rate'].split('/'))
                            if den != 0:
                                metadata['fps'] = num / den
                        break
            
            # Duration
            if 'format' in data:
                metadata['duration'] = float(data['format'].get('duration', 0))
    
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass
    
    # Fallback to filesystem date if no metadata date
    if metadata['creation_date'] is None:
        stat = filepath.stat()
        metadata['creation_date'] = datetime.fromtimestamp(stat.st_birthtime if hasattr(stat, 'st_birthtime') else stat.st_mtime)
    
    return metadata