#!/usr/bin/env bash
#
# Shared NO_AWS helpers.
#
# NO_AWS switches the demo between the cross-cloud topology (loyalty and sales
# federated from AWS Glue) and a GCP-only topology (both seeded natively into
# FROYO_NATIVE_DATASET). The accepted spellings must stay in sync with
# agent/config/agent_definition.py:env_flag, otherwise the shell scripts and the
# agent definition can disagree about where the tables live.

#######################################
# Report whether the demo is running in GCP-only mode.
# Globals:
#   NO_AWS
# Returns:
#   0 when NO_AWS is one of 1/true/yes/on (case-insensitive), 1 otherwise.
#######################################
is_no_aws() {
  local value
  value="$(echo "${NO_AWS:-false}" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')"
  case "${value}" in
    1 | true | yes | on) return 0 ;;
    *) return 1 ;;
  esac
}

#######################################
# Echo the fully-qualified name of a loyalty/sales table for the active mode.
# Globals:
#   GCP_PROJECT, FROYO_NATIVE_DATASET, FEDERATED_CATALOG, GLUE_DATABASE
# Arguments:
#   $1 - table name (e.g. "${FROYO_LOYALTY_TABLE}")
# Outputs:
#   The three-part native ref, or the four-part P.C.N.T federated ref.
#######################################
analytics_table_ref() {
  local table="$1"
  if is_no_aws; then
    echo "${GCP_PROJECT}.${FROYO_NATIVE_DATASET}.${table}"
  else
    echo "${GCP_PROJECT}.${FEDERATED_CATALOG}.${GLUE_DATABASE}.${table}"
  fi
}
