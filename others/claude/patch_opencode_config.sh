#!/bin/bash

#######################################
# Patches OpenCode config to include CODE_STANDARDS.md in instructions.
#
# OpenCode only auto-reads ~/.claude/CLAUDE.md for global rules.
# Additional files like CODE_STANDARDS.md must be explicitly listed
# in the opencode.json "instructions" array.
#
# This script creates or patches ~/.config/opencode/opencode.json
# to include the CODE_STANDARDS.md reference.
#
# Globals: HOME
# Arguments: None
# Outputs: Patch status messages with color-coded output
#######################################

set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

CONFIG_DIR="${HOME}/.config/opencode"
CONFIG_FILE="${CONFIG_DIR}/opencode.json"
INSTRUCTION_ENTRY="${HOME}/.claude/CODE_STANDARDS.md"

echo "Patching OpenCode config to include CODE_STANDARDS.md..."
echo -e "Config: ${GREEN}${CONFIG_FILE}${NC}"
echo ""

# Check that python3 is available
if ! command -v python3 &>/dev/null; then
  echo -e "${RED}Error: python3 is required but not found.${NC}"
  exit 1
fi

# Ensure config directory exists
mkdir -p "${CONFIG_DIR}"

# Create or patch the config file
if [[ ! -f "${CONFIG_FILE}" ]]; then
  # No config file exists -- create a minimal one
  python3 -c "
import json, sys

config = {
    '\$schema': 'https://opencode.ai/config.json',
    'instructions': [sys.argv[1]]
}

with open(sys.argv[2], 'w') as f:
    json.dump(config, f, indent=2)
    f.write('\n')
" "${INSTRUCTION_ENTRY}" "${CONFIG_FILE}"

  echo -e "${GREEN}Created ${CONFIG_FILE} with instructions entry.${NC}"
else
  # Config file exists -- check and patch
  RESULT=$(python3 -c "
import json, sys

entry = sys.argv[1]
config_path = sys.argv[2]

with open(config_path, 'r') as f:
    config = json.load(f)

instructions = config.get('instructions', [])

if entry in instructions:
    print('ALREADY_EXISTS')
    sys.exit(0)

# Back up before modifying
import shutil
shutil.copy2(config_path, config_path + '.bak')

instructions.append(entry)
config['instructions'] = instructions

with open(config_path, 'w') as f:
    json.dump(config, f, indent=2)
    f.write('\n')

print('PATCHED')
" "${INSTRUCTION_ENTRY}" "${CONFIG_FILE}")

  if [[ "${RESULT}" == "ALREADY_EXISTS" ]]; then
    echo -e "${YELLOW}Instructions entry already exists, skipping.${NC}"
  elif [[ "${RESULT}" == "PATCHED" ]]; then
    echo -e "${GREEN}Patched ${CONFIG_FILE} with instructions entry.${NC}"
    echo -e "${YELLOW}Backup saved to ${CONFIG_FILE}.bak${NC}"
  else
    echo -e "${RED}Unexpected result: ${RESULT}${NC}"
    exit 1
  fi
fi

echo ""
echo -e "${GREEN}Done.${NC} OpenCode will now load CODE_STANDARDS.md in all sessions."
echo ""
echo "Verify with: cat ${CONFIG_FILE}"
