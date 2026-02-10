#!/bin/bash

#######################################
# Syncs agent rule files to Gemini CLI global rules directory
# using symlinks instead of copies.
#
# Creates symlinks in ~/.gemini/ pointing back to the repo's
# agent_stuff/ directory, so changes to the source files are
# immediately reflected without re-running the script.
#
# Globals: HOME
# Arguments: None
# Outputs: Sync status messages with color-coded output
#######################################

set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Resolve script directory and source
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$(cd "${SCRIPT_DIR}/../../agent_stuff" && pwd)"
TARGET_DIR="${HOME}/.gemini"

# File mappings: parallel arrays for Bash 3.2 compatibility.
# AGENTS.md is renamed to GEMINI.md because Gemini CLI
# reads ~/.gemini/GEMINI.md as the global instructions file.
SOURCE_NAMES=("AGENTS.md" "CODE_STANDARDS.md")
TARGET_NAMES=("GEMINI.md" "CODE_STANDARDS.md")

echo "Syncing agent rules to Gemini global directory (symlinks)..."
echo -e "Source: ${GREEN}${SOURCE_DIR}${NC}"
echo -e "Target: ${GREEN}${TARGET_DIR}${NC}"
echo ""

# Ensure target directory exists
mkdir -p "${TARGET_DIR}"

# Sync each file
for i in "${!SOURCE_NAMES[@]}"; do
  source_name="${SOURCE_NAMES[${i}]}"
  target_name="${TARGET_NAMES[${i}]}"
  source_file="${SOURCE_DIR}/${source_name}"
  target_file="${TARGET_DIR}/${target_name}"

  if [[ ! -f "${source_file}" ]]; then
    echo -e "${YELLOW}Warning: ${source_file} not found, skipping${NC}"
    continue
  fi

  # Handle existing target
  if [[ -L "${target_file}" ]]; then
    # Existing symlink -- remove and recreate
    rm "${target_file}"
  elif [[ -f "${target_file}" ]]; then
    # Existing regular file -- back up before replacing
    backup_file="${target_file}.bak"
    echo -e "${YELLOW}Backing up existing ${target_name} to ${target_name}.bak${NC}"
    mv "${target_file}" "${backup_file}"
  fi

  # Create symlink with absolute path
  ln -s "${source_file}" "${target_file}"

  echo -e "${GREEN}Linked ${source_name} -> ${target_file}${NC}"
done

echo ""
echo -e "${GREEN}Sync complete.${NC} Symlinks created in ${TARGET_DIR}/"
echo ""

# Patch settings.json
if [[ -f "${SCRIPT_DIR}/patch_settings.json.sh" ]]; then
  "${SCRIPT_DIR}/patch_settings.json.sh"
fi

echo "Verify with: ls -la ${TARGET_DIR}/"
