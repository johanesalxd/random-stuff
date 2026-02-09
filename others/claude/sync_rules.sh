#!/bin/bash

#######################################
# Syncs agent rule files to Claude/OpenCode global rules directory
# using symlinks instead of copies.
#
# Creates symlinks in ~/.claude/ pointing back to the repo's
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
TARGET_DIR="${HOME}/.claude"

# File mappings: source_name:target_name
# AGENTS.md is renamed to CLAUDE.md because Claude CLI and OpenCode
# read ~/.claude/CLAUDE.md as the global instructions file.
declare -A FILE_MAP=(
  ["AGENTS.md"]="CLAUDE.md"
  ["CODE_STANDARDS.md"]="CODE_STANDARDS.md"
)

echo "Syncing agent rules to Claude global directory (symlinks)..."
echo -e "Source: ${GREEN}${SOURCE_DIR}${NC}"
echo -e "Target: ${GREEN}${TARGET_DIR}${NC}"
echo ""

# Ensure target directory exists
mkdir -p "${TARGET_DIR}"

# Sync each file
for source_name in "${!FILE_MAP[@]}"; do
  target_name="${FILE_MAP[${source_name}]}"
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

# Patch OpenCode config
if [[ -f "${SCRIPT_DIR}/patch_opencode_config.sh" ]]; then
  "${SCRIPT_DIR}/patch_opencode_config.sh"
fi

echo "Verify with: ls -la ${TARGET_DIR}/"
