# Media Archive Migration Toolkit

A comprehensive system for migrating, organizing, and managing 4TB+ media archives with automatic deduplication, metadata extraction, and hash verification.

## Features

- **Automated Analysis**: Scans existing archive, extracts metadata from video files
- **Duplicate Detection**: Uses BLAKE3 hashing to identify exact duplicates
- **Smart Organization**: Organizes by device and date while preserving project structures
- **Hash Verification**: Ensures every file copied correctly
- **Progress Tracking**: Rich progress bars and detailed logging
- **Resumable**: Can restart migration if interrupted
- **Safe**: Never modifies source files, only copies to target

## Quick Start

### 1. Setup

```bash
# Clone repository
git clone https://github.com/yourusername/media-archive-toolkit.git
cd media-archive-toolkit

# Create environment and install dependencies
make setup

# Activate environment
source .venv/bin/activate
```

### 2. Configure

Edit `config/device_mappings.yaml` to match your setup:

```yaml
devices:
  sony-fx-3: CAM_fx3
  sony-fx-30: CAM_fx30
  # ... add your devices
```

### 3. Analyze (This Week - Before NAS Arrives)

```bash
# Dry run first (quick preview)
make analyze-dry

# Full analysis (4-6 hours)
make analyze
```

This creates:
- `analysis_results/migration_manifest.json` - Complete migration plan
- `analysis_results/duplicates_report.csv` - All duplicate files found
- `analysis_results/analysis_summary.txt` - Human-readable summary

### 4. Review Results

```bash
# View summary
cat analysis_results/analysis_summary.txt

# Check duplicates
make duplicates

# Generate HTML report (optional)
make report
```

### 5. Migrate (When NAS Arrives)

```bash
# Connect your NAS, verify it's mounted at /Volumes/RodNAS

# Create folder structure on NAS
make create-structure

# Dry run first (preview)
make migrate-dry

# Execute migration (8-12 hours)
# IMPORTANT: Run in tmux/screen so it doesn't stop if connection drops
tmux new-session -s migration
make migrate
```

### 6. Verify

```bash
# Verify all files copied correctly
make verify
```

If verification passes 100%, you can safely clean the source SSD.

## Project Structure

```
media-archive-toolkit/
├── config/
│   └── device_mappings.yaml    # Device and project configuration
├── src/
│   └── media_toolkit/
│       ├── analyzer.py          # Analysis engine
│       ├── migrator.py          # Migration engine
│       ├── verifier.py          # Verification engine
│       ├── models.py            # Data models
│       └── utils/               # Hash, ffprobe, YAML utilities
├── scripts/
│   └── create_structure.sh     # NAS folder creation
├── tests/
├── pyproject.toml
├── Makefile
└── README.md
```

## Target NAS Structure

After migration, your NAS will be organized like this:

```
/Volumes/RodNAS/Media/
├── Originals/              # Immutable vault - NEVER delete
│   ├── CAM_fx3/
│   │   └── 2025/
│   │       └── 2025-10-03/
│   │           ├── C0048.MP4
│   │           └── C0049.MP4
│   ├── CAM_fx30/
│   ├── CAM_zv-e10/
│   ├── CAM_osmo-pocket-3/
│   ├── CAM_riverside/      # Riverside.fm cloud recordings
│   ├── AUDIO_zoom-f3/
│   └── AUDIO_dji-mic-2/
│       └── 2024/
│           └── 2024-02-14/
│               └── DJI_01_20240214_192834.WAV
│
├── Projects/               # Project-specific organization
│   ├── aipe/
│   │   └── aipe-podcast/
│   │       └── 2025-05-09_jentic.../
│   │           ├── 00-raw/
│   │           ├── 01-edited/
│   │           └── metadata.yaml
│   ├── capcut/
│   │   └── renders/        # CapCut exports (User Data excluded)
│   ├── video_mama_2025/
│   └── billionblog/
│
├── Catalog/                # System metadata
│   ├── catalog.sqlite      # Searchable database
│   ├── sidecars/           # YAML metadata for each file
│   ├── transcripts/        # Future: Whisper transcriptions
│   └── thumbs/             # Future: Thumbnail previews
│
└── _ingest/                # Temporary staging (for future imports)
```

## Configuration

### Device Mappings

Edit `config/device_mappings.yaml`:

```yaml
devices:
  sony-fx-3: CAM_fx3
  sony-fx-30: CAM_fx30
  sony-zv-e10: CAM_zv-e10
  dji-osmo-pocket-3: CAM_osmo-pocket-3
  zoom-f3: AUDIO_zoom-f3
  dji-mic-2: AUDIO_dji-mic-2

# Projects that preserve internal structure
projects:
  - name: aipe-footage
    source_path: aipe-footage
    target_path: /Projects/aipe
    preserve_structure: true
```

### Duplicate Handling

The toolkit automatically detects duplicates and keeps the best copy based on priority:

1. Files in `/Originals/CAM_*` (camera raw footage)
2. Files in `/Originals/AUDIO_*` (audio recordings)
3. Files in `/Projects/aipe` (structured projects)
4. Other project files

## Commands Reference

### Setup
- `make setup` - Create environment and install dependencies
- `make check-volumes` - Verify source/target volumes exist

### Analysis (This Week)
- `make analyze` - Full analysis with hash computation (4-6 hours)
- `make analyze-dry` - Quick preview without hashing
- `make report` - Generate HTML summary report
- `make duplicates` - Show duplicate statistics

### Migration (When NAS Arrives)
- `make create-structure` - Create folder structure on NAS
- `make migrate` - Execute migration (8-12 hours)
- `make migrate-dry` - Preview migration without copying
- `make verify` - Verify all files copied correctly

### Utilities
- `make clean` - Clean analysis results and cache
- `make test` - Run tests

## What Gets Excluded

The following are automatically excluded from migration:

- System files: `.DS_Store`, `*.db`, `.sync_*`
- macOS folders: `.fseventsd`, `.Spotlight-V100`, `.Trashes`
- CapCut app data: `capcut/User Data/`
- Temporary files: `*.tmp`, `*.temp`

## Duplicate Detection

The toolkit uses BLAKE3 hashing to identify exact duplicates:

1. **Scan**: Computes hash for every file
2. **Group**: Groups files with identical hashes
3. **Prioritize**: Selects primary copy based on location
4. **Report**: Lists all duplicates with space savings

Expected space savings: **400-800GB** from your 4TB archive.

## Safety Features

- **Read-only source**: Never modifies original files
- **Hash verification**: Every copied file is verified
- **Resumable**: Can restart if interrupted
- **Dry-run mode**: Preview everything before executing
- **Detailed logging**: Complete audit trail
- **Error handling**: Continues on errors, logs everything

## Troubleshooting

### "Source volume not found"
```bash
# Check current volumes
ls -la /Volumes/
# Update Makefile if your volume name differs
```

### "Analysis taking too long"
```bash
# Run in background with nohup
nohup make analyze > analysis.log 2>&1 &
# Check progress
tail -f analysis.log
```

### "Migration failed partway"
```bash
# Just run migrate again - it skips existing files
make migrate
```

### "Verification shows missing files"
```bash
# Check the verification_errors.log
cat verification_errors.log
# Re-run migration for failed files
make migrate
```

## Timeline

- **Week 1 (Now)**: Run analysis on current SSD (~4-6 hours runtime)
- **Week 1-2**: Review results, approve migration plan
- **Week 2**: NAS arrives, create structure
- **Week 2**: Execute migration (~8-12 hours)
- **Week 2**: Verify migration, update cloud backup
- **Week 3+**: Clean SSD, start using new structure

## Future Features (Phase 2)

Once migration is complete, you can add:

- **Whisper transcription**: Search footage by spoken content
- **Thumbnail generation**: Visual previews in catalog
- **Semantic search**: Find clips by description
- **Auto-tagging**: YOLO object detection
- **n8n automation**: Automated ingest for new footage
- **Web UI**: Streamlit search interface

## Support

If you encounter issues:

1. Check `make help` for all commands
2. Review log files in `analysis_results/`
3. Run with `--dry-run` to preview
4. Open an issue on GitHub with logs

## License

MIT License - See LICENSE file

## Credits

Built following the QuackVerse development pattern with UV + pyproject.toml + Makefile for reproducible, self-contained tooling.

---

**Remember**: The source SSD stays untouched until verification passes 100%. You have a complete cloud backup as additional safety.