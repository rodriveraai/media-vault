#!/bin/bash
set -euo pipefail

# new_shoot.sh
# Adds a new shoot to an existing project structure.
#
# Usage:
#   ./new_shoot.sh <project-name> <shoot-location> [YYYY-MM-DD]
#   # Optionally, specify the project directory explicitly:
#   PROJECT_DIR="/Volumes/RodNAS/Media/Projects/2025/2025-10-05_billion_ep-024" ./new_shoot.sh billion_ep-024 london_office 2025-10-12
#
# Notes:
# - If PROJECT_DIR is not provided, this script searches under $PROJECTS_ROOT for "*_<project-name>".
# - If multiple matches are found, it will abort and list them.

# ---------- Config ----------
PROJECTS_ROOT="/Volumes/RodNAS/Media/Projects"
: "${PROJECTS_ROOT:?PROJECTS_ROOT must be set}"
if [ ! -d "/Volumes/RodNAS" ]; then
  echo "❌ /Volumes/RodNAS is not mounted. Aborting."
  exit 1
fi

if [ $# -lt 2 ]; then
  echo "Usage: $0 <project-name> <shoot-location> [YYYY-MM-DD]"
  exit 1
fi

PROJECT_NAME="$1"
SHOOT_LOCATION="$2"
DATE_INPUT="${3:-}"
if [ -z "$DATE_INPUT" ]; then
  DATE="$(date +%Y-%m-%d)"
else
  DATE="$DATE_INPUT"
fi
YEAR="${DATE%%-*}"

# Standard device lanes (keep in sync with scaffolder)
VIDEO_CAMS=( "CAM_fx3" "CAM_fx30" "CAM_zv-e10" "CAM_osmo-pocket-3" "CAM_riverside" )
AUDIO_DEVS=( "RECORDER_zoom-f3" "MIC_dji-mic-2" "MIC_osmo-pocket-3" )
STILLS_CAMS=( "CAM_fx3" "CAM_fx30" "CAM_zv-e10" "CAM_osmo-pocket-3" )

# ---------- Locate project directory ----------
if [ -n "${PROJECT_DIR:-}" ]; then
  BASE_DIR="$PROJECT_DIR"
  if [ ! -d "$BASE_DIR" ]; then
    echo "❌ PROJECT_DIR '$BASE_DIR' does not exist."
    exit 1
  fi
else
  # Search pattern */*_<PROJECT_NAME> (year/date_project)
  mapfile -t CANDIDATES < <(find "$PROJECTS_ROOT" -maxdepth 2 -type d -name "*_${PROJECT_NAME}" 2>/dev/null | sort)
  if [ "${#CANDIDATES[@]}" -eq 0 ]; then
    echo "❌ No project directory found for name '${PROJECT_NAME}' under '${PROJECTS_ROOT}'."
    echo "   Expected something like: ${PROJECTS_ROOT}/YYYY/DDDD-${PROJECT_NAME}"
    echo "   Tip: set PROJECT_DIR explicitly when calling this script."
    exit 1
  elif [ "${#CANDIDATES[@]}" -gt 1 ]; then
    echo "❌ Multiple project directories found for '${PROJECT_NAME}'. Please set PROJECT_DIR explicitly."
    printf ' - %s\n' "${CANDIDATES[@]}"
    exit 1
  else
    BASE_DIR="${CANDIDATES[0]}"
  fi
fi

SHOOT_DIR="${BASE_DIR}/02_shoots/${DATE}_${SHOOT_LOCATION}"

# ---------- Create directories ----------
if [ -d "$SHOOT_DIR" ]; then
  echo "⚠️  Shoot directory already exists: $SHOOT_DIR"
else
  echo "➕ Creating shoot: $SHOOT_DIR"
  mkdir -p "${SHOOT_DIR}/VIDEO" "${SHOOT_DIR}/AUDIO" "${SHOOT_DIR}/STILLS"
fi

# VIDEO lanes
for cam in "${VIDEO_CAMS[@]}"; do
  mkdir -p "${SHOOT_DIR}/VIDEO/${cam}"
done

# AUDIO lanes
for aud in "${AUDIO_DEVS[@]}"; do
  mkdir -p "${SHOOT_DIR}/AUDIO/${aud}"
done

# STILLS lanes
for still in "${STILLS_CAMS[@]}"; do
  mkdir -p "${SHOOT_DIR}/STILLS/${still}"
done

# Mirror per-camera structure in selects & proxies (tidy for editors)
for cam in "${VIDEO_CAMS[@]}"; do
  mkdir -p "${BASE_DIR}/03_selects/${DATE}_${SHOOT_LOCATION}/VIDEO/${cam}"
  mkdir -p "${BASE_DIR}/04_proxies/${DATE}_${SHOOT_LOCATION}/VIDEO/${cam}"
done
for aud in "${AUDIO_DEVS[@]}"; do
  mkdir -p "${BASE_DIR}/03_selects/${DATE}_${SHOOT_LOCATION}/AUDIO/${aud}"
  mkdir -p "${BASE_DIR}/04_proxies/${DATE}_${SHOOT_LOCATION}/AUDIO/${aud}"
done

# ---------- Write/Update shoot manifest ----------
cat > "${SHOOT_DIR}/shoot.yaml" << YAML
shoot:
  project: ${PROJECT_NAME}
  date: ${DATE}
  location: ${SHOOT_LOCATION}
  video_devices:
$(for cam in "${VIDEO_CAMS[@]}"; do echo "    - ${cam#CAM_}"; done)
  audio_devices:
$(for aud in "${AUDIO_DEVS[@]}"; do echo "    - ${aud#RECORDER_}"; done)
  notes: ""
YAML

# ---------- Append to project-level metadata.yaml ----------
METADATA="${BASE_DIR}/metadata.yaml"
if [ ! -f "$METADATA" ]; then
  echo "⚠️  metadata.yaml not found, creating a new one."
  cat > "$METADATA" << YAML
project_name: ${PROJECT_NAME}
created_date: ${DATE}
status: active
notes: ""
shoots:
  - date: ${DATE}
    location: ${SHOOT_LOCATION}
    expected_video_devices: [$(printf '"%s",' "${VIDEO_CAMS[@]#"CAM_"}" | sed 's/,$//')]
    expected_audio_devices: [$(printf '"%s",' "${AUDIO_DEVS[@]#"RECORDER_"}" | sed 's/,$//')]
YAML
else
  # Append to the shoots array (simple YAML append; assumes file uses the same structure)
  echo "📝 Updating metadata.yaml"
  {
    echo "  - date: ${DATE}"
    echo "    location: ${SHOOT_LOCATION}"
    printf "    expected_video_devices: ["
    printf '"%s",' "${VIDEO_CAMS[@]#"CAM_"}" | sed 's/,$//'
    echo "]"
    printf "    expected_audio_devices: ["
    printf '"%s",' "${AUDIO_DEVS[@]#"RECORDER_"}" | sed 's/,$//'
    echo "]"
  } >> "$METADATA"
fi

# ---------- Update README.md ----------
README="${BASE_DIR}/README.md"
if [ ! -f "$README" ]; then
  echo "⚠️  README.md not found, creating a new one."
  cat > "$README" << MD
# ${PROJECT_NAME}

Created (shoot added): ${DATE}

## Structure
See 02_shoots for new shoot folders.

## Shoots
### ${DATE} - ${SHOOT_LOCATION}
- Manifest: \`02_shoots/${DATE}_${SHOOT_LOCATION}/shoot.yaml\`
- After ingest, run proxies:
  \`./generate_proxies.sh "${BASE_DIR}/02_shoots/${DATE}_${SHOOT_LOCATION}"\`
MD
else
  {
    echo ""
    echo "### ${DATE} - ${SHOOT_LOCATION}"
    echo "- Manifest: \`02_shoots/${DATE}_${SHOOT_LOCATION}/shoot.yaml\`"
    echo "- After ingest, run proxies:"
    echo "  \`./generate_proxies.sh \"${BASE_DIR}/02_shoots/${DATE}_${SHOOT_LOCATION}\"\`"
  } >> "$README"
fi

echo "✅ New shoot added:"
echo "   • ${SHOOT_DIR}"
echo "   • Updated: ${METADATA}"
echo "   • Updated: ${README}"
echo
echo "Next steps:"
echo "  1) Dump cards to /Media/_ingest"
echo "  2) Run ingest.py with:"
echo "     python ingest.py --in /Media/_ingest --project \"${PROJECT_NAME}\" --shoot \"${DATE}_${SHOOT_LOCATION}\" --device <fx3|fx30|zv-e10|osmo-pocket-3|riverside> --track VIDEO --date \"${DATE}\""
echo "  3) (For audio) use --track AUDIO and device names matching: zoom-f3, dji-mic-2, osmo-pocket-3"
echo "  4) Generate proxies as needed (see README)."
