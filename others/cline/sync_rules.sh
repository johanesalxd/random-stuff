#!/bin/bash

#######################################
# Syncs agent rule files to Cline global rules directory.
# Globals: None
# Arguments: None
# Outputs: Sync status messages
#######################################

set -euo pipefail

# Resolve script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$(cd "${SCRIPT_DIR}/../../agent_stuff" && pwd)"
TARGET_DIR="${HOME}/Documents/Cline/Rules"

# Files to sync
FILES=("AGENTS.md" "CODE_STANDARDS.md")

echo "Syncing agent rules to Cline global directory..."
echo "Source: ${SOURCE_DIR}"
echo "Target: ${TARGET_DIR}"
echo ""

# Ensure target directory exists
mkdir -p "${TARGET_DIR}"

# Sync each file
for file in "${FILES[@]}"; do
  source_file="${SOURCE_DIR}/${file}"
  target_file="${TARGET_DIR}/${file}"

  if [[ ! -f "${source_file}" ]]; then
    echo "Warning: ${source_file} not found, skipping"
    continue
  fi

  # Remove write protection if target exists
  if [[ -f "${target_file}" ]]; then
    chmod 644 "${target_file}"
  fi

  # Copy file
  cp "${source_file}" "${target_file}"

  # Apply read-only protection
  chmod 444 "${target_file}"

  echo "✓ Synced ${file}"
done

echo ""
echo "Sync complete. Files are now read-only (444)."
