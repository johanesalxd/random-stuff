#!/bin/bash

#######################################
# Patches Gemini CLI settings to include global context files.
#
# When context.fileName is defined in settings.json, it overrides
# the default loading of ~/.gemini/GEMINI.md. We must explicitly
# list both GEMINI.md and CODE_STANDARDS.md.
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

CONFIG_FILE="${HOME}/.gemini/settings.json"
REQUIRED_ENTRIES=("GEMINI.md" "CODE_STANDARDS.md")

echo "Patching Gemini CLI config to include global context files..."
echo -e "Config: ${GREEN}${CONFIG_FILE}${NC}"
echo ""

# Check that python3 is available
if ! command -v python3 &>/dev/null; then
  echo -e "${RED}Error: python3 is required but not found.${NC}"
  exit 1
fi

# Create or patch the config file
if [[ ! -f "${CONFIG_FILE}" ]]; then
  # No config file exists -- create a minimal one
  python3 -c "
import json, sys

entries = sys.argv[1].split(',')
config_path = sys.argv[2]

config = {
    'context': {
        'fileName': entries
    }
}

with open(config_path, 'w') as f:
    json.dump(config, f, indent=2)
    f.write('\n')
" "$(IFS=,; echo "${REQUIRED_ENTRIES[*]}")" "${CONFIG_FILE}"

  echo -e "${GREEN}Created ${CONFIG_FILE} with required context.fileName entries.${NC}"
else
  # Config file exists -- check and patch
  RESULT=$(python3 -c "
import json, sys

required_entries = sys.argv[1].split(',')
config_path = sys.argv[2]

with open(config_path, 'r') as f:
    try:
        config = json.load(f)
    except json.JSONDecodeError:
        print('ERROR_DECODE')
        sys.exit(1)

context = config.get('context', {})
file_names = context.get('fileName', [])

# Check if all required entries are present
missing = [e for e in required_entries if e not in file_names]

if not missing:
    print('ALREADY_EXISTS')
    sys.exit(0)

# Back up before modifying
import shutil
shutil.copy2(config_path, config_path + '.bak')

# Add missing entries
for entry in missing:
    file_names.append(entry)

context['fileName'] = file_names
config['context'] = context

with open(config_path, 'w') as f:
    json.dump(config, f, indent=2)
    f.write('\n')

print('PATCHED')
" "$(IFS=,; echo "${REQUIRED_ENTRIES[*]}")" "${CONFIG_FILE}")

  if [[ "${RESULT}" == "ALREADY_EXISTS" ]]; then
    echo -e "${YELLOW}All context entries already exist, skipping.${NC}"
  elif [[ "${RESULT}" == "PATCHED" ]]; then
    echo -e "${GREEN}Patched ${CONFIG_FILE} with missing context entries.${NC}"
    echo -e "${YELLOW}Backup saved to ${CONFIG_FILE}.bak${NC}"
  elif [[ "${RESULT}" == "ERROR_DECODE" ]]; then
    echo -e "${RED}Error: Failed to decode JSON in ${CONFIG_FILE}.${NC}"
    exit 1
  else
    echo -e "${RED}Unexpected result: ${RESULT}${NC}"
    exit 1
  fi
fi

echo ""
echo -e "${GREEN}Done.${NC} Gemini CLI will now load global context files."
echo ""
echo "Verify with: cat ${CONFIG_FILE}"
