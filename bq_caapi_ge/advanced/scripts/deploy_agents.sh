#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

usage() {
    cat << 'EOF'
Usage: deploy_agents.sh [OPTIONS]

Deploys the Semantic Analytics Agent to Vertex AI Agent Engine.

Options:
  --stage-only <DIR>   Stage the deployment bundle into <DIR> without deploying.
  -h, --help           Show this help message and exit.
EOF
}

STAGE_DIR=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --stage-only)
            if [[ $# -lt 2 ]]; then
                echo "Error: --stage-only requires a directory argument" >&2
                exit 1
            fi
            STAGE_DIR="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Error: Unknown argument: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

# If .env exists in REPO_ROOT, load it
if [[ -f "$REPO_ROOT/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$REPO_ROOT/.env"
    set +a
fi

stage_bundle() {
    local target_stage="$1"
    local agent_stage="$target_stage/agents/semantic_analytics"

    mkdir -p "$target_stage/agents"
    touch "$target_stage/agents/__init__.py"

    mkdir -p "$agent_stage"
    cp "$REPO_ROOT/advanced/app/semantic_analytics/__init__.py" "$agent_stage/"
    cp "$REPO_ROOT/advanced/app/semantic_analytics/agent.py" "$agent_stage/"

    mkdir -p "$agent_stage/semantic"
    cp "$REPO_ROOT/semantic/"*.py "$agent_stage/semantic/"

    mkdir -p "$agent_stage/config/semantic_contracts"
    cp "$REPO_ROOT/config/__init__.py" "$agent_stage/config/"
    cp "$REPO_ROOT/config/ca_locations.py" "$agent_stage/config/"
    cp "$REPO_ROOT/config/gcp_auth.py" "$agent_stage/config/"
    cp "$REPO_ROOT/config/semantic_contracts/"*.yaml "$agent_stage/config/semantic_contracts/"

    cat > "$agent_stage/requirements.txt" << 'EOF'
anthropic[vertex]>=0.78
google-adk>=2.0.0
google-cloud-bigquery>=3.42.2
google-cloud-dataplex>=2.13.0
google-cloud-geminidataanalytics>=0.9.0
python-dotenv>=1.2.1
pyyaml>=6.0.3
requests>=2.32.0
EOF

    # Note: adk deploy strips GOOGLE_CLOUD_PROJECT and injects the hosting project,
    # so BQ_COMPUTE_PROJECT preserves explicit query billing project override.
    # Secrets like SQL_ROLE_ASSERTION_HMAC_SECRET, OAUTH_CLIENT_SECRET, and FLASK_SECRET_KEY are NEVER copied here.
    local deploy_auth_mode="${DEPLOY_SQL_AUTH_MODE:-user}"
    case "$deploy_auth_mode" in
        user|impersonated_sa)
            ;;
        adc)
            echo "Error: Shared ADC mode ('adc') cannot be deployed to multi-user Agent Engine." >&2
            exit 1
            ;;
        *)
            echo "Error: Invalid DEPLOY_SQL_AUTH_MODE: '$deploy_auth_mode'. Allowed values: 'user', 'impersonated_sa'." >&2
            exit 1
            ;;
    esac

    local canonical_role_map=""
    if [[ "$deploy_auth_mode" == "impersonated_sa" ]]; then
        if [[ -z "${SQL_ROLE_TRUSTED_CALLER_SA:-}" ]]; then
            echo "Error: SQL_ROLE_TRUSTED_CALLER_SA must be set when DEPLOY_SQL_AUTH_MODE=impersonated_sa" >&2
            exit 1
        fi
        if [[ -z "${SQL_ROLE_SA_MAP_JSON:-}" ]]; then
            echo "Error: SQL_ROLE_SA_MAP_JSON must be set when DEPLOY_SQL_AUTH_MODE=impersonated_sa" >&2
            exit 1
        fi
        canonical_role_map="$(PYTHONPATH="$REPO_ROOT" python3 -c '
import json, os, re, sys
from semantic.rls_impersonation import parse_role_sa_map, _CUSTOMER_SA_REGEX, _is_google_managed_sa

trusted_sa = os.environ.get("SQL_ROLE_TRUSTED_CALLER_SA", "").strip()
if not _CUSTOMER_SA_REGEX.match(trusted_sa) or _is_google_managed_sa(trusted_sa):
    sys.exit(f"Error: Invalid customer-managed service account for SQL_ROLE_TRUSTED_CALLER_SA: {trusted_sa!r}")

aud = os.environ.get("SQL_ROLE_ASSERTION_AUDIENCE", "bq-caapi-rls").strip() or "bq-caapi-rls"
if not re.match(r"^[A-Za-z0-9._:-]{1,128}$", aud):
    sys.exit(f"Error: Invalid SQL_ROLE_ASSERTION_AUDIENCE: {aud!r}")

state_key = os.environ.get("ADK_ROLE_ASSERTION_STATE_KEY", "bq-caapi-role-assertion").strip() or "bq-caapi-role-assertion"
if not re.match(r"^[A-Za-z0-9_-]{1,128}$", state_key):
    sys.exit(f"Error: Invalid ADK_ROLE_ASSERTION_STATE_KEY: {state_key!r}")

try:
    lifetime = int(os.environ.get("SQL_IMPERSONATION_LIFETIME_SECONDS", "300"))
    if not (60 <= lifetime <= 3600):
        raise ValueError("out of range")
except Exception:
    sys.exit("Error: SQL_IMPERSONATION_LIFETIME_SECONDS must be an integer between 60 and 3600")

try:
    max_ttl = int(os.environ.get("SQL_ROLE_ASSERTION_MAX_TTL_SECONDS", "900"))
    if not (60 <= max_ttl <= 3600):
        raise ValueError("out of range")
except Exception:
    sys.exit("Error: SQL_ROLE_ASSERTION_MAX_TTL_SECONDS must be an integer between 60 and 3600")

role_map_raw = os.environ.get("SQL_ROLE_SA_MAP_JSON")
m = parse_role_sa_map(role_map_raw)
print(json.dumps(m, separators=(",", ":")))
')"
    fi

    cat > "$agent_stage/.env" << EOF
SQL_AUTH_MODE=$deploy_auth_mode
ADK_OAUTH_TOKEN_STATE_KEY=${ADK_OAUTH_TOKEN_STATE_KEY:-${AUTH_RESOURCE_SEMANTIC_ANALYTICS:-bq-caapi-oauth-semantic}}
BIGQUERY_LOCATION=${BIGQUERY_LOCATION:-US}
CATALOG_ALLOWED_PROJECTS=${CATALOG_ALLOWED_PROJECTS:-bigquery-public-data}
CATALOG_ALLOWED_DATASETS=${CATALOG_ALLOWED_DATASETS:-bigquery-public-data.thelook_ecommerce}
SEMANTIC_SELECTOR_MODEL=${SEMANTIC_SELECTOR_MODEL:-gemini-3.5-flash}
SQL_GENERATOR_MODEL=${SQL_GENERATOR_MODEL:-claude-sonnet-4-5}
RESULT_SUMMARIZER_MODEL=${RESULT_SUMMARIZER_MODEL:-gemini-3.5-flash}
SQL_MAX_BYTES_BILLED=${SQL_MAX_BYTES_BILLED:-1000000000}
EOF
    if [[ -n "${BQ_COMPUTE_PROJECT:-}" ]]; then
        echo "BQ_COMPUTE_PROJECT=$BQ_COMPUTE_PROJECT" >> "$agent_stage/.env"
    fi

    if [[ "$deploy_auth_mode" == "impersonated_sa" ]]; then
        cat >> "$agent_stage/.env" << EOF
SQL_ROLE_TRUSTED_CALLER_SA=$SQL_ROLE_TRUSTED_CALLER_SA
SQL_ROLE_ASSERTION_AUDIENCE=${SQL_ROLE_ASSERTION_AUDIENCE:-bq-caapi-rls}
ADK_ROLE_ASSERTION_STATE_KEY=${ADK_ROLE_ASSERTION_STATE_KEY:-bq-caapi-role-assertion}
SQL_IMPERSONATION_LIFETIME_SECONDS=${SQL_IMPERSONATION_LIFETIME_SECONDS:-300}
SQL_ROLE_ASSERTION_MAX_TTL_SECONDS=${SQL_ROLE_ASSERTION_MAX_TTL_SECONDS:-900}
SQL_ROLE_SA_MAP_JSON='$canonical_role_map'
EOF
    fi
}

if [[ -n "$STAGE_DIR" ]]; then
    stage_bundle "$STAGE_DIR"
    echo "Staged Semantic Analytics Agent bundle into: $STAGE_DIR"
    exit 0
fi

# Live deployment mode
if [[ ! -f "$REPO_ROOT/.env" ]]; then
    echo "Error: .env file not found in $REPO_ROOT" >&2
    exit 1
fi

if [[ -z "${GOOGLE_CLOUD_PROJECT:-}" ]]; then
    echo "Error: GOOGLE_CLOUD_PROJECT must be set in .env" >&2
    exit 1
fi

STAGE_TMP="$(mktemp -d)"
trap 'rm -rf "$STAGE_TMP"' EXIT

stage_bundle "$STAGE_TMP"

REGION="${AGENT_ENGINE_LOCATION:-us-central1}"
DISPLAY_NAME="Semantic Analytics Agent"

echo "Deploying $DISPLAY_NAME to Vertex AI Agent Engine..."
echo "  Project: $GOOGLE_CLOUD_PROJECT"
echo "  Region:  $REGION"

(
    cd "$REPO_ROOT"
    uv run --frozen adk deploy agent_engine "$STAGE_TMP/agents/semantic_analytics" \
        --project="$GOOGLE_CLOUD_PROJECT" \
        --region="$REGION" \
        --display_name="$DISPLAY_NAME"
)

echo "Deployment complete."
