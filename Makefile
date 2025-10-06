GREEN  := $(shell tput -Txterm setaf 2)
YELLOW := $(shell tput -Txterm setaf 3)
BLUE   := $(shell tput -Txterm setaf 4)
RED    := $(shell tput -Txterm setaf 1)
RESET  := $(shell tput -Txterm sgr0)

PYTHON_VERSION := 3.13
VENV_NAME := .venv
PYTHON := $(VENV_NAME)/bin/python
SOURCE_VOLUME := /Volumes/RodMedia
TARGET_VOLUME := /Volumes/RodNAS/Media

.PHONY: help
help:
	@echo ''
	@echo '$(YELLOW)═══════════════════════════════════════════════════════════════════$(RESET)'
	@echo '$(YELLOW)                  Media Archive Migration Toolkit$(RESET)'
	@echo '$(YELLOW)═══════════════════════════════════════════════════════════════════$(RESET)'
	@echo ''
	@echo '$(BLUE)PHASE 0: Initial Setup$(RESET)'
	@echo '  $(GREEN)make setup$(RESET)              - Create Python environment and install dependencies'
	@echo '  $(GREEN)make check-volumes$(RESET)      - Verify source/target volumes are accessible'
	@echo ''
	@echo '$(BLUE)PHASE 1: Analysis (Before NAS Arrives)$(RESET)'
	@echo '  $(GREEN)make analyze-dry$(RESET)        - Quick scan without hash computation (20 min)'
	@echo '  $(GREEN)make analyze$(RESET)            - Full analysis with duplicate detection (4-6 hours)'
	@echo '                              Computes BLAKE3 hashes, detects duplicates'
	@echo ''
	@echo '$(BLUE)PHASE 2: Migration (When NAS Arrives)$(RESET)'
	@echo '  $(GREEN)make migrate$(RESET)            - Copy files to NAS with verification (8-12 hours)'
	@echo '                              Creates folder structure, copies files, verifies hashes'
	@echo '  $(GREEN)make verify$(RESET)             - Verify all files copied correctly'
	@echo '                              Run before deleting source files!'
	@echo ''
	@echo '$(BLUE)PHASE 3: Ongoing Workflow$(RESET)'
	@echo '  $(GREEN)make index-catalog$(RESET)      - Index YAML sidecars into searchable SQLite database'
	@echo '  $(GREEN)make link-project$(RESET)       - Link footage into project structure'
	@echo '                              Usage: make link-project PROJECT=ep-024 SHOOT=london DATE=2025-10-06 DEVICES="fx3 fx30"'
	@echo ''
	@echo '$(BLUE)Utilities$(RESET)'
	@echo '  $(GREEN)make structure$(RESET)          - Show project file tree'
	@echo '  $(GREEN)make clean$(RESET)              - Clean analysis results and Python cache'
	@echo '  $(GREEN)make aggregate <dir>$(RESET)    - Aggregate source files into single document'
	@echo '  $(GREEN)make add-paths$(RESET)          - Add file paths as comments to Python files'
	@echo ''
	@echo '$(YELLOW)───────────────────────────────────────────────────────────────────$(RESET)'
	@echo '$(YELLOW)Typical Workflow:$(RESET)'
	@echo '  1. make setup              → Install dependencies'
	@echo '  2. make analyze-dry        → Preview what will be analyzed'
	@echo '  3. make analyze            → Full analysis (run in tmux overnight)'
	@echo '  4. Review analysis_results/ → Check duplicates_report.csv'
	@echo '  5. [Wait for NAS to arrive]'
	@echo '  6. make migrate            → Copy to NAS (run in tmux)'
	@echo '  7. make verify             → Confirm 100% success'
	@echo '  8. make index-catalog      → Build searchable database'
	@echo '$(YELLOW)───────────────────────────────────────────────────────────────────$(RESET)'
	@echo ''

.PHONY: setup
setup:
	@echo "$(BLUE)Creating virtual environment...$(RESET)"
	uv venv --python $(PYTHON_VERSION)
	uv pip install -e ".[dev]" --python $(VENV_NAME)/bin/python
	@echo "$(GREEN)Done! Run: source $(VENV_NAME)/bin/activate$(RESET)"

.PHONY: check-volumes
check-volumes:
	@echo "$(BLUE)Checking volumes...$(RESET)"
	@test -d "$(SOURCE_VOLUME)" || (echo "$(RED)Source not found$(RESET)" && exit 1)
	@echo "$(GREEN)Source OK: $(SOURCE_VOLUME)$(RESET)"

.PHONY: analyze-dry
analyze-dry: check-volumes
	$(PYTHON) -m media_toolkit.analyzer --source $(SOURCE_VOLUME) --output ./analysis_results --dry-run

.PHONY: analyze
analyze: check-volumes
	@echo "$(YELLOW)This takes 4-6 hours. Press Enter to continue...$(RESET)"
	@read dummy
	$(PYTHON) -m media_toolkit.analyzer --source $(SOURCE_VOLUME) --output ./analysis_results

.PHONY: migrate
migrate:
	@echo "$(YELLOW)This takes 8-12 hours. Press Enter to continue...$(RESET)"
	@read dummy
	$(PYTHON) -m media_toolkit.migrator --manifest ./analysis_results/migration_manifest.json --target $(TARGET_VOLUME)

.PHONY: verify
verify:
	$(PYTHON) -m media_toolkit.verifier --manifest ./analysis_results/migration_manifest.json --target $(TARGET_VOLUME)

.PHONY: clean
clean:
	rm -rf ./analysis_results .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

.PHONY: structure
structure: ## Show project structure
	@echo "${YELLOW}Current Project Structure:${RESET}"
	@echo "${BLUE}"
	@if command -v tree > /dev/null; then \
		tree -a -I '.git|.venv|__pycache__|*.pyc|*.pyo|*.pyd|.pytest_cache|.ruff_cache|.coverage|htmlcov'; \
	else \
		find . -not -path '*/\.*' -not -path '*.pyc' -not -path '*/__pycache__/*' \
			-not -path './.venv/*' -not -path './build/*' -not -path './dist/*' \
			-not -path './*.egg-info/*' \
			| sort | \
			sed -e "s/[^-][^\/]*\// │   /g" -e "s/├── /│── /" -e "s/└── /└── /"; \
	fi
	@echo "${RESET}"

.PHONY: aggregate
aggregate: ## Aggregate text files from a directory (usage: make aggregate <directory>)
	@echo "${BLUE}Aggregating files from: ${AGGREGATE_TARGET}${RESET}"
	@# Create the aggregate script in memory and execute it
	@echo '#!/bin/bash' > .temp_aggregate.sh
	@echo '# Temporary aggregation script generated by Makefile' >> .temp_aggregate.sh
	@echo 'set -euo pipefail' >> .temp_aggregate.sh
	@echo '' >> .temp_aggregate.sh
	@echo '# Ensure Homebrew coreutils gnubin is on PATH (for grealpath/realpath on macOS)' >> .temp_aggregate.sh
	@echo 'if [ -d "/opt/homebrew/opt/coreutils/libexec/gnubin" ]; then' >> .temp_aggregate.sh
	@echo '  export PATH="/opt/homebrew/opt/coreutils/libexec/gnubin:$$PATH"' >> .temp_aggregate.sh
	@echo 'fi' >> .temp_aggregate.sh
	@echo '' >> .temp_aggregate.sh
	@echo 'portable_realpath() {' >> .temp_aggregate.sh
	@echo '  if command -v realpath >/dev/null 2>&1; then' >> .temp_aggregate.sh
	@echo '    realpath "$$1"' >> .temp_aggregate.sh
	@echo '  elif command -v grealpath >/dev/null 2>&1; then' >> .temp_aggregate.sh
	@echo '    grealpath "$$1"' >> .temp_aggregate.sh
	@echo '  elif command -v python3 >/dev/null 2>&1; then' >> .temp_aggregate.sh
	@echo '    python3 -c "import os,sys; print(os.path.abspath(os.path.expanduser(sys.argv[1])))" "$$1"' >> .temp_aggregate.sh
	@echo '  else' >> .temp_aggregate.sh
	@echo '    if [ -d "$$1" ]; then (cd "$$1" && pwd -P); else (cd "$$(dirname "$$1")" && printf "%s/%s\n" "$$PWD" "$$(basename "$$1")"); fi' >> .temp_aggregate.sh
	@echo '  fi' >> .temp_aggregate.sh
	@echo '}' >> .temp_aggregate.sh
	@echo '' >> .temp_aggregate.sh
	@echo 'INPUT_ARG="$$1"' >> .temp_aggregate.sh
	@echo 'INPUT_PATH="$$(portable_realpath "$$INPUT_ARG")"' >> .temp_aggregate.sh
	@echo 'if [ ! -d "$$INPUT_PATH" ]; then' >> .temp_aggregate.sh
	@echo '  echo "incorrect path"' >> .temp_aggregate.sh
	@echo '  echo "  pwd       : $$PWD"' >> .temp_aggregate.sh
	@echo '  echo "  input arg : $$INPUT_ARG"' >> .temp_aggregate.sh
	@echo '  echo "  resolved  : $$INPUT_PATH"' >> .temp_aggregate.sh
	@echo '  echo "hint: run from repo root, e.g. make aggregate ./quack-core/src/quack_core/config"' >> .temp_aggregate.sh
	@echo '  exit 1' >> .temp_aggregate.sh
	@echo 'fi' >> .temp_aggregate.sh
	@echo '' >> .temp_aggregate.sh
	@echo 'TRANSIENT_DIR="$$INPUT_PATH/_transient-files"' >> .temp_aggregate.sh
	@echo 'TIMESTAMP="$$(date +%Y-%m-%d)"' >> .temp_aggregate.sh
	@echo 'DIRECTORY_NAME="$$(basename "$$INPUT_PATH")"' >> .temp_aggregate.sh
	@echo 'OUTPUT_FILE="$$TRANSIENT_DIR/$$TIMESTAMP-$$DIRECTORY_NAME.txt"' >> .temp_aggregate.sh
	@echo 'USE_GITIGNORE=false' >> .temp_aggregate.sh
	@echo 'if [ -f "$$INPUT_PATH/.gitignore" ] && command -v git >/dev/null 2>&1; then' >> .temp_aggregate.sh
	@echo '  USE_GITIGNORE=true' >> .temp_aggregate.sh
	@echo 'fi' >> .temp_aggregate.sh
	@echo 'mkdir -p "$$TRANSIENT_DIR"' >> .temp_aggregate.sh
	@echo 'if [ ! -f "$$OUTPUT_FILE" ]; then' >> .temp_aggregate.sh
	@echo '  : > "$$OUTPUT_FILE"' >> .temp_aggregate.sh
	@echo '  echo "Created output file: $$OUTPUT_FILE"' >> .temp_aggregate.sh
	@echo 'else' >> .temp_aggregate.sh
	@echo '  echo "Output file already exists: $$OUTPUT_FILE"' >> .temp_aggregate.sh
	@echo 'fi' >> .temp_aggregate.sh
	@echo '' >> .temp_aggregate.sh
	@echo 'file_already_added() {' >> .temp_aggregate.sh
	@echo '  local file="$$1"' >> .temp_aggregate.sh
	@echo '  grep -q "here is $$file:" "$$OUTPUT_FILE" || return 1' >> .temp_aggregate.sh
	@echo '}' >> .temp_aggregate.sh
	@echo '' >> .temp_aggregate.sh
	@echo 'is_ignored_by_gitignore() {' >> .temp_aggregate.sh
	@echo '  local path="$$1"' >> .temp_aggregate.sh
	@echo '  if $$USE_GITIGNORE; then git -C "$$INPUT_PATH" check-ignore "$$path" >/dev/null 2>&1; return $$?; fi' >> .temp_aggregate.sh
	@echo '  return 1' >> .temp_aggregate.sh
	@echo '}' >> .temp_aggregate.sh
	@echo '' >> .temp_aggregate.sh
	@echo 'FILE_EXTENSIONS=("*.txt" "*.md" "*.py" "*.yaml" "*.template" "*.toml" "Makefile" "*.ts" "*.tsx" "*.mdx" "*.js" "*.jsx")' >> .temp_aggregate.sh
	@echo 'FILES_ADDED=0' >> .temp_aggregate.sh
	@echo 'FILES_PROCESSED=0' >> .temp_aggregate.sh
	@echo 'for EXT in "$${FILE_EXTENSIONS[@]}"; do' >> .temp_aggregate.sh
	@echo '  while IFS= read -r FILE; do' >> .temp_aggregate.sh
	@echo '    FILEPATH="$$(portable_realpath "$$FILE")"' >> .temp_aggregate.sh
	@echo '    if [[ "$$FILEPATH" == "$$TRANSIENT_DIR"* ]] || is_ignored_by_gitignore "$$FILEPATH"; then' >> .temp_aggregate.sh
	@echo '      continue' >> .temp_aggregate.sh
	@echo '    fi' >> .temp_aggregate.sh
	@echo '    FILENAME="$$(basename "$$FILE")"' >> .temp_aggregate.sh
	@echo '    if [[ "$$FILENAME" == deprecated_* ]]; then' >> .temp_aggregate.sh
	@echo '      echo "Skipping deprecated file: $$FILEPATH"' >> .temp_aggregate.sh
	@echo '      continue' >> .temp_aggregate.sh
	@echo '    fi' >> .temp_aggregate.sh
	@echo '    ((FILES_PROCESSED++))' >> .temp_aggregate.sh
	@echo '    if file_already_added "$$FILEPATH"; then' >> .temp_aggregate.sh
	@echo '      echo "Skipping already added file: $$FILEPATH"' >> .temp_aggregate.sh
	@echo '      continue' >> .temp_aggregate.sh
	@echo '    fi' >> .temp_aggregate.sh
	@echo '    echo "Processing: $$FILEPATH"' >> .temp_aggregate.sh
	@echo '    echo "here is $$FILEPATH:" >> "$$OUTPUT_FILE"' >> .temp_aggregate.sh
	@echo '    echo "<$$FILENAME>" >> "$$OUTPUT_FILE"' >> .temp_aggregate.sh
	@echo '    cat "$$FILE" >> "$$OUTPUT_FILE"' >> .temp_aggregate.sh
	@echo '    echo "</$$FILENAME>" >> "$$OUTPUT_FILE"' >> .temp_aggregate.sh
	@echo '    echo "" >> "$$OUTPUT_FILE"' >> .temp_aggregate.sh
	@echo '    ((FILES_ADDED++))' >> .temp_aggregate.sh
	@echo '  done < <(find "$$INPUT_PATH" -type f -name "$$EXT" ! -path "$$TRANSIENT_DIR/*" ! -name ".*")' >> .temp_aggregate.sh
	@echo 'done' >> .temp_aggregate.sh
	@echo '' >> .temp_aggregate.sh
	@echo 'if [ $$FILES_PROCESSED -eq 0 ]; then' >> .temp_aggregate.sh
	@echo '  echo "No files found matching the specified criteria. Exiting."' >> .temp_aggregate.sh
	@echo '  exit 0' >> .temp_aggregate.sh
	@echo 'fi' >> .temp_aggregate.sh
	@echo 'if [ $$FILES_ADDED -eq 0 ]; then' >> .temp_aggregate.sh
	@echo '  echo "No new files to add. Exiting."' >> .temp_aggregate.sh
	@echo '  exit 0' >> .temp_aggregate.sh
	@echo 'else' >> .temp_aggregate.sh
	@echo '  echo "All files aggregated into: $$OUTPUT_FILE"' >> .temp_aggregate.sh
	@echo '  exit 0' >> .temp_aggregate.sh
	@echo 'fi' >> .temp_aggregate.sh
	@chmod +x .temp_aggregate.sh
	@./.temp_aggregate.sh "$(AGGREGATE_TARGET)"
	@rm -f .temp_aggregate.sh
	@echo "${GREEN}✓ File aggregation completed${RESET}"

.PHONY: add-paths
add-paths: ## Add file paths as first-line comments to all Python files
	@echo "${BLUE}Adding file paths as comments to Python files...${RESET}"
	@echo '#!/usr/bin/env python' > add_paths.py
	@echo '# add_paths.py' >> add_paths.py
	@echo '"""' >> add_paths.py
	@echo 'Script to add file paths as first-line comments to Python files.' >> add_paths.py
	@echo '"""' >> add_paths.py
	@echo 'import os' >> add_paths.py
	@echo 'import sys' >> add_paths.py
	@echo 'import traceback' >> add_paths.py
	@echo '' >> add_paths.py
	@echo 'def update_file(filepath):' >> add_paths.py
	@echo '    try:' >> add_paths.py
	@echo '        relpath = os.path.relpath(filepath)' >> add_paths.py
	@echo '        print(f"Processing {relpath}...")' >> add_paths.py
	@echo '' >> add_paths.py
	@echo '        with open(filepath, "r") as f:' >> add_paths.py
	@echo '            content = f.read()' >> add_paths.py
	@echo '' >> add_paths.py
	@echo '        lines = content.split("\\n")' >> add_paths.py
	@echo '        if not lines:' >> add_paths.py
	@echo '            print(f"  Skipping {relpath}: empty file")' >> add_paths.py
	@echo '            return' >> add_paths.py
	@echo '' >> add_paths.py
	@echo '        has_path_comment = False' >> add_paths.py
	@echo '        if lines[0].strip().startswith("#"):' >> add_paths.py
	@echo '            has_path_comment = True' >> add_paths.py
	@echo '            old_line = lines[0]' >> add_paths.py
	@echo '            lines[0] = f"# {relpath}"' >> add_paths.py
	@echo '            print(f"  Replacing comment: {old_line} -> # {relpath}")' >> add_paths.py
	@echo '        else:' >> add_paths.py
	@echo '            lines.insert(0, f"# {relpath}")' >> add_paths.py
	@echo '            print(f"  Adding new comment: # {relpath}")' >> add_paths.py
	@echo '' >> add_paths.py
	@echo '        with open(filepath, "w") as f:' >> add_paths.py
	@echo '            f.write("\\n".join(lines))' >> add_paths.py
	@echo '' >> add_paths.py
	@echo '        print(f"  Updated {relpath}")' >> add_paths.py
	@echo '    except Exception as e:' >> add_paths.py
	@echo '        print(f"  Error processing {filepath}: {str(e)}")' >> add_paths.py
	@echo '        traceback.print_exc()' >> add_paths.py
	@echo '' >> add_paths.py
	@echo 'def main():' >> add_paths.py
	@echo '    try:' >> add_paths.py
	@echo '        count = 0' >> add_paths.py
	@echo '        print("Starting file scan...")' >> add_paths.py
	@echo '        for root, dirs, files in os.walk("."):' >> add_paths.py
	@echo '            # Skip hidden and build directories' >> add_paths.py
	@echo '            if any(x in root for x in [".git", ".venv", "__pycache__", ".mypy_cache",' >> add_paths.py
	@echo '                                      ".pytest_cache", ".ruff_cache", "build", "dist", ".egg-info"]):' >> add_paths.py
	@echo '                continue' >> add_paths.py
	@echo '' >> add_paths.py
	@echo '            for file in files:' >> add_paths.py
	@echo '                if file.endswith(".py"):' >> add_paths.py
	@echo '                    filepath = os.path.join(root, file)' >> add_paths.py
	@echo '                    update_file(filepath)' >> add_paths.py
	@echo '                    count += 1' >> add_paths.py
	@echo '' >> add_paths.py
	@echo '        print(f"Processed {count} Python files")' >> add_paths.py
	@echo '    except Exception as e:' >> add_paths.py
	@echo '        print(f"Fatal error: {str(e)}")' >> add_paths.py
	@echo '        traceback.print_exc()' >> add_paths.py
	@echo '        sys.exit(1)' >> add_paths.py
	@echo '' >> add_paths.py
	@echo 'if __name__ == "__main__":' >> add_paths.py
	@echo '    main()' >> add_paths.py
	@chmod +x add_paths.py
	@$(PYTHON) add_paths.py
	@rm add_paths.py
	@echo "${GREEN}✓ File paths added to all Python files${RESET}"

# Dummy target for directory arguments to aggregate
%:
	@:

.PHONY: index-catalog
index-catalog:
	$(PYTHON) -m media_toolkit.catalog index-sidecars \
	  --catalog /Volumes/RodNAS/Media/Catalog/catalog.sqlite \
	  --root /Volumes/RodNAS/Media

.PHONY: link-project
link-project:
	$(PYTHON) -m media_toolkit.link_into_project \
	  --root /Volumes/RodNAS/Media \
	  --project $(PROJECT) \
	  --shoot $(SHOOT) \
	  --date $(DATE) \
	  $(foreach d,$(DEVICES),--device $(d))


.DEFAULT_GOAL := help
