# Getting Started Guide

## Prerequisites

- **macOS** (tested on 15.4.1)
- **Python 3.10+** (will be installed via UV)
- **UV** package manager: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **ffmpeg** (optional, for video metadata): `brew install ffmpeg`

## Step-by-Step Setup

### 1. Clone Repository

```bash
cd ~/Projects  # or wherever you keep code
git clone https://github.com/yourusername/media-archive-toolkit.git
cd media-archive-toolkit
```

### 2. Install Dependencies

```bash
# This creates virtual environment and installs everything
make setup

# Activate the environment
source .venv/bin/activate
```

### 3. Verify Installation

```bash
# Check volumes are accessible
make check-volumes

# Should show:
# ✓ Source volume found: /Volumes/RodMedia
# ⚠ Target volume not found (expected): /Volumes/RodNAS/Media
```

### 4. Review Configuration

```bash
# Edit device mappings if needed
nano config/device_mappings.yaml

# The defaults should work for your setup:
# - sony-fx-3 → CAM_fx3
# - sony-fx-30 → CAM_fx30
# - etc.
```

### 5. Test with Dry Run

```bash
# Quick preview (no hashing, just scans files)
make analyze-dry

# This should complete in ~10-20 minutes
# Shows what WOULD be analyzed without actually computing hashes
```

### 6. Full Analysis

```bash
# IMPORTANT: This takes 4-6 hours
# Run in tmux/screen so it doesn't stop if your session disconnects

# Start tmux
tmux new-session -s analysis

# Run analysis
make analyze

# Detach from tmux: Ctrl+b, then d
# Reattach later: tmux attach -t analysis
```

### 7. Review Results

After analysis completes:

```bash
# Read the summary
cat analysis_results/analysis_summary.txt

# Check duplicate statistics
make duplicates

# Review the full manifest (JSON)
less analysis_results/migration_manifest.json

# Look at duplicate report (CSV)
open analysis_results/duplicates_report.csv
```

### 8. When NAS Arrives

```bash
# 1. Connect NAS, verify it mounts at /Volumes/RodNAS

# 2. Create folder structure
make create-structure

# 3. Preview migration
make migrate-dry

# 4. Execute migration (in tmux!)
tmux new-session -s migration
make migrate

# 5. Verify everything copied correctly
make verify

# 6. If verification passes 100%, you can clean the SSD
```

## Troubleshooting

### "UV not found"
```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add to PATH (add to ~/.zshrc or ~/.bashrc)
export PATH="$HOME/.cargo/bin:$PATH"

# Reload shell
source ~/.zshrc
```

### "ffmpeg not found"
```bash
# Install via Homebrew
brew install ffmpeg

# Verify
ffmpeg -version
```

### "Permission denied" errors
```bash
# Make scripts executable
chmod +x scripts/*.sh

# Or just use make commands (they handle this)
make create-structure
```

### Analysis is slow
This is normal. With 4TB of data:
- Scanning files: ~5-10 minutes
- Computing hashes: ~4-6 hours (BLAKE3 is fast, but 4TB is a lot)
- Extracting metadata: included in above

Run in tmux/screen and let it run overnight.

## What to Expect

### Analysis Phase
- **Time**: 4-6 hours
- **Output**: 3 files in `analysis_results/`
  - `migration_manifest.json` (~50-100MB)
  - `duplicates_report.csv` (~1-5MB)
  - `analysis_summary.txt` (~10KB)
- **Action**: Review these files, especially duplicates

### Migration Phase
- **Time**: 8-12 hours (depends on NAS speed)
- **Action**: Let it run in tmux, check progress occasionally
- **Safety**: Can be interrupted and resumed

### Verification Phase
- **Time**: 2-4 hours
- **Action**: Must pass 100% before cleaning source SSD

## Common Questions

**Q: Can I pause and resume?**
A: Yes! The migrator checks if files already exist and skips them. Just run `make migrate` again.

**Q: What if I find errors?**
A: Check the error logs. Most common: file permissions, disk full, network issues. Fix and re-run.

**Q: How much space will I save?**
A: Expect 400-800GB from deduplication based on your archive.

**Q: Can I migrate in batches?**
A: Yes! Edit the manifest JSON to only include certain files, or modify the Makefile `--batch-size` parameter.

**Q: What if my NAS has a different path?**
A: Edit the Makefile and change `TARGET_VOLUME := /Volumes/RodNAS/Media` to your actual path.

## Next Steps After Migration

Once migration is verified:

1. **Update cloud backup** to sync from NAS instead of SSD
2. **Test workflow** - import new footage using new structure
3. **Add advanced features**:
   - Whisper transcription
   - Web search UI
   - Automated ingest pipeline
4. **Document your workflow** for future reference

## Getting Help

- Check `make help` for all available commands
- Review error logs in `analysis_results/`
- Read the main README.md for detailed explanations
- Open GitHub issue with logs if stuck

Happy organizing! 🎥