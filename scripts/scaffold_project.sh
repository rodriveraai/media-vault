#!/bin/bash
set -euo pipefail

# Usage: ./new_project.sh <project-name> [shoot-location]
# Example: ./new_project.sh billion_ep-024 london_office

if [ $# -lt 1 ]; then
  echo "Usage: $0 <project-name> [shoot-location]"
  exit 1
fi

PROJECT_NAME="$1"
SHOOT_LOCATION="${2:-shoot_01}"

DATE="$(date +%Y-%m-%d)"
YEAR="$(date +%Y)"

# CHANGE THIS ROOT IF NEEDED
PROJECTS_ROOT="/Volumes/RodNAS/Media/Projects"
BASE_DIR="${PROJECTS_ROOT}/${YEAR}/${DATE}_${PROJECT_NAME}"
SHOOT_DIR="${BASE_DIR}/02_shoots/${DATE}_${SHOOT_LOCATION}"

# Validate mount
if [ ! -d "/Volumes/RodNAS" ]; then
  echo "❌ /Volumes/RodNAS is not mounted. Aborting."
  exit 1
fi

echo "Creating project structure: ${BASE_DIR}"

# Main project folders
mkdir -p "${BASE_DIR}/00_admin"
mkdir -p "${BASE_DIR}/01_assets"
mkdir -p "${SHOOT_DIR}/VIDEO"
mkdir -p "${SHOOT_DIR}/AUDIO"
mkdir -p "${SHOOT_DIR}/STILLS"
mkdir -p "${BASE_DIR}/03_selects"
mkdir -p "${BASE_DIR}/04_proxies"
mkdir -p "${BASE_DIR}/05_renders"
mkdir -p "${BASE_DIR}/06_deliverables"

# Standard device lanes (VIDEO)
for cam in CAM_fx3 CAM_fx30 CAM_zv-e10 CAM_osmo-pocket-3 CAM_riverside; do
  mkdir -p "${SHOOT_DIR}/VIDEO/${cam}"
done

# AUDIO devices
for aud in RECORDER_zoom-f3 MIC_dji-mic-2 MIC_osmo-pocket-3; do
  mkdir -p "${SHOOT_DIR}/AUDIO/${aud}"
done

# STILLS lanes (photos/screenshots)
for still in CAM_fx3 CAM_fx30 CAM_zv-e10 CAM_osmo-pocket-3; do
  mkdir -p "${SHOOT_DIR}/STILLS/${still}"
done

# Mirror per-camera structure in selects & proxies (keeps things tidy for editors)
for cam in CAM_fx3 CAM_fx30 CAM_zv-e10 CAM_osmo-pocket-3 CAM_riverside; do
  mkdir -p "${BASE_DIR}/03_selects/${DATE}_${SHOOT_LOCATION}/VIDEO/${cam}"
  mkdir -p "${BASE_DIR}/04_proxies/${DATE}_${SHOOT_LOCATION}/VIDEO/${cam}"
done
for aud in RECORDER_zoom-f3 MIC_dji-mic-2 MIC_osmo-pocket-3; do
  mkdir -p "${BASE_DIR}/03_selects/${DATE}_${SHOOT_LOCATION}/AUDIO/${aud}"
  mkdir -p "${BASE_DIR}/04_proxies/${DATE}_${SHOOT_LOCATION}/AUDIO/${aud}"
done

# Renders & Deliverables common targets
for p in youtube shorts reels tiktok podcast-audio linkedin x; do
  mkdir -p "${BASE_DIR}/05_renders/${p}"
  mkdir -p "${BASE_DIR}/06_deliverables/${p}"
done

# Project metadata
cat > "${BASE_DIR}/metadata.yaml" << YAML
project_name: ${PROJECT_NAME}
created_date: ${DATE}
status: active
notes: ""
shoots:
  - date: ${DATE}
    location: ${SHOOT_LOCATION}
    expected_video_devices: ["fx3","fx30","zv-e10","osmo-pocket-3","riverside"]
    expected_audio_devices: ["zoom-f3","dji-mic-2","osmo-pocket-3"]
YAML

# Shoot-level manifest (ingest can read/enrich this)
cat > "${SHOOT_DIR}/shoot.yaml" << YAML
shoot:
  project: ${PROJECT_NAME}
  date: ${DATE}
  location: ${SHOOT_LOCATION}
  video_devices:
    - fx3
    - fx30
    - zv-e10
    - osmo-pocket-3
    - riverside
  audio_devices:
    - zoom-f3
    - dji-mic-2
    - osmo-pocket-3
  notes: ""
YAML

# Project README
cat > "${BASE_DIR}/README.md" << MD
# ${PROJECT_NAME}

Created: ${DATE}

## Structure

- \`00_admin/\` — Briefs, scripts, call sheets
- \`01_assets/\` — Logos, LUTs, music, graphics
- \`02_shoots/\` — Raw footage by shoot date/location
  - \`${DATE}_${SHOOT_LOCATION}/VIDEO/CAM_* ->\` symlinks to /Originals after ingest
  - \`${DATE}_${SHOOT_LOCATION}/AUDIO/... ->\` symlinks to /Originals after ingest
  - \`${DATE}_${SHOOT_LOCATION}/STILLS/CAM_*/\`
- \`03_selects/\` — Editor picks (mirrors camera lanes)
- \`04_proxies/\` — Editing proxies (mirrors camera lanes)
- \`05_renders/\` — Exports (youtube, shorts, reels, etc.)
- \`06_deliverables/\` — Final assets by platform

## Shoot

### ${DATE} • ${SHOOT_LOCATION}
- Manifest: \`02_shoots/${DATE}_${SHOOT_LOCATION}/shoot.yaml\`
- After ingest, run proxies:
  \`./generate_proxies.sh "${BASE_DIR}/02_shoots/${DATE}_${SHOOT_LOCATION}"\`

## Editor handoff
- Generate CSV:
  \`export_for_editor.py --project ${PROJECT_NAME} --shoot ${DATE}_${SHOOT_LOCATION} --out "${BASE_DIR}/clips.csv"\`
- Share \`04_proxies/\` + \`clips.csv\`
MD

echo "✓ Project created: ${BASE_DIR}"
echo
echo "Next:"
echo "  1) Dump cards to /Media/_ingest and run ingest.py with --project ${PROJECT_NAME} --shoot ${DATE}_${SHOOT_LOCATION}"
echo "  2) Symlinks will appear in 02_shoots/.../VIDEO/* after ingest (don’t move Originals)"
echo "  3) Run proxy script on the shoot folder if needed"
echo "  4) Export clips.csv for the editor"
