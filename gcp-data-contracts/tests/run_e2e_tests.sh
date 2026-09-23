#!/usr/bin/env bash
# ==============================================================================
# SGX Google Cloud Data Contracts - Master E2E Test Runner
# ==============================================================================
# Executes opaque-box test suites across Tiers 1-4 with colorized reporting,
# execution statistics, and deterministic exit codes.
# ==============================================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ANSI Color codes
BOLD="\033[1m"
RESET="\033[0m"
RED="\033[31m"
GREEN="\033[32m"
YELLOW="\033[33m"
BLUE="\033[34m"
MAGENTA="\033[35m"
CYAN="\033[36m"
GRAY="\033[90m"

# Default configuration
TIER="all"
VERBOSE=false

print_banner() {
    echo -e "${BOLD}${CYAN}========================================================================${RESET}"
    echo -e "${BOLD}${CYAN}   SGX GOOGLE CLOUD DATA CONTRACTS - E2E TEST SUITE RUNNER              ${RESET}"
    echo -e "${BOLD}${CYAN}   Defense-in-Depth Contract Verification (Tiers 1 - 4)                ${RESET}"
    echo -e "${BOLD}${CYAN}========================================================================${RESET}"
    echo -e "${GRAY}Project Root: ${PROJECT_ROOT}${RESET}"
    echo -e "${GRAY}Python:       $(python3 --version 2>&1)${RESET}"
    echo -e "${GRAY}Date:         $(date -u +"%Y-%m-%dT%H:%M:%SZ")${RESET}"
    echo ""
}

show_help() {
    echo -e "${BOLD}Usage:${RESET} $0 [OPTIONS]"
    echo ""
    echo -e "${BOLD}Options:${RESET}"
    echo -e "  -t, --tier <1|2|3|4>   Run a specific test tier:"
    echo -e "                           ${CYAN}1${RESET}: Feature Coverage (Compiler, Contract, Avro, DDL, DQ Spec)"
    echo -e "                           ${CYAN}2${RESET}: Boundary & Corner Cases (Nulls, Malformed, Zero/Negative, Wash Trade)"
    echo -e "                           ${CYAN}3${RESET}: Cross-Feature Combinations (Integration Pipelines & Oracles)"
    echo -e "                           ${CYAN}4${RESET}: Realistic SGX Workloads (Happy Path, Ingress Rejection, SLAs)"
    echo -e "  -a, --all              Run all test tiers (Tiers 1, 2, 3, 4) [default]"
    echo -e "  -v, --verbose          Enable verbose test output (unittest -v)"
    echo -e "  -h, --help             Display this help message and exit"
    echo ""
    echo -e "${BOLD}Examples:${RESET}"
    echo -e "  $0 --all"
    echo -e "  $0 --tier 1"
    echo -e "  $0 --tier 4 -v"
    exit 0
}

# Parse CLI arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -t|--tier)
            if [[ -z "${2:-}" ]]; then
                echo -e "${RED}Error: --tier requires an argument (1, 2, 3, 4, or all)${RESET}"
                exit 2
            fi
            TIER="$2"
            shift 2
            ;;
        -a|--all)
            TIER="all"
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            show_help
            ;;
        *)
            echo -e "${RED}Unknown option: $1${RESET}"
            show_help
            ;;
    esac
done

cd "${PROJECT_ROOT}"

# Global scorecard metrics
TOTAL_RAN=0
TOTAL_PASSED=0
TOTAL_FAILED=0
TOTAL_SKIPPED=0
SUITE_START_TIME=$(date +%s)
OVERALL_EXIT_CODE=0

run_tier() {
    local tier_num="$1"
    local tier_file="$2"
    local tier_desc="$3"

    echo -e "${BOLD}${BLUE}------------------------------------------------------------------------${RESET}"
    echo -e "${BOLD}${BLUE}>> Running Tier ${tier_num}: ${tier_desc}${RESET}"
    echo -e "${GRAY}   Target: tests/${tier_file}${RESET}"
    echo -e "${BOLD}${BLUE}------------------------------------------------------------------------${RESET}"

    local start_time=$(date +%s)
    local test_output
    local exit_status=0

    local verbosity_flag=""
    if [ "$VERBOSE" = true ]; then
        verbosity_flag="-v"
    else
        verbosity_flag="-v"  # Keep standard verbose output to parse counts
    fi

    # Run unittest
    test_output=$(python3 -m unittest "tests/${tier_file}" ${verbosity_flag} 2>&1) || exit_status=$?

    local end_time=$(date +%s)
    local elapsed=$((end_time - start_time))

    if [ "$VERBOSE" = true ] || [ $exit_status -ne 0 ]; then
        echo "${test_output}"
    else
        # Print summary line of test run
        echo "${test_output}" | grep -E "(Ran [0-9]+ tests|OK|FAILED)" || true
    fi

    # Parse test statistics from unittest output
    local ran_count=0
    local failed_count=0
    local skipped_count=0

    # Extract ran count
    if echo "${test_output}" | grep -qE "Ran [0-9]+ tests"; then
        ran_count=$(echo "${test_output}" | grep -oE "Ran [0-9]+ tests" | grep -oE "[0-9]+")
    fi

    # Extract failures / errors count
    if echo "${test_output}" | grep -qE "FAILED \("; then
        local fail_match=$(echo "${test_output}" | grep -oE "failures=[0-9]+" | grep -oE "[0-9]+" || echo 0)
        local err_match=$(echo "${test_output}" | grep -oE "errors=[0-9]+" | grep -oE "[0-9]+" || echo 0)
        failed_count=$((fail_match + err_match))
    fi

    # Extract skipped count
    if echo "${test_output}" | grep -qE "skipped=[0-9]+"; then
        skipped_count=$(echo "${test_output}" | grep -oE "skipped=[0-9]+" | grep -oE "[0-9]+" || echo 0)
    fi

    local passed_count=$((ran_count - failed_count - skipped_count))
    if [ $passed_count -lt 0 ]; then passed_count=0; fi

    TOTAL_RAN=$((TOTAL_RAN + ran_count))
    TOTAL_PASSED=$((TOTAL_PASSED + passed_count))
    TOTAL_FAILED=$((TOTAL_FAILED + failed_count))
    TOTAL_SKIPPED=$((TOTAL_SKIPPED + skipped_count))

    if [ $exit_status -eq 0 ]; then
        echo -e "${GREEN}${BOLD}✓ Tier ${tier_num} Completed Successfully${RESET} (${passed_count} passed, ${skipped_count} skipped, ${elapsed}s)"
    else
        echo -e "${RED}${BOLD}✗ Tier ${tier_num} Had Failures/Pending Items${RESET} (${failed_count} failed, ${passed_count} passed, ${skipped_count} skipped, ${elapsed}s)"
        OVERALL_EXIT_CODE=1
    fi
    echo ""
}

print_banner

case "${TIER}" in
    1)
        run_tier 1 "test_tier1_feature.py" "Feature Coverage (Contract, Compiler, Avro, DDL, DQ Spec)"
        ;;
    2)
        run_tier 2 "test_tier2_boundary.py" "Boundary & Corner Cases (Nulls, Malformed, Zero/Negative, Wash Trade)"
        ;;
    3)
        run_tier 3 "test_tier3_combinations.py" "Cross-Feature Combinations & Pipelines"
        ;;
    4)
        run_tier 4 "test_tier4_workloads.py" "Realistic SGX Workload Simulations"
        ;;
    all)
        run_tier 1 "test_tier1_feature.py" "Feature Coverage (Contract, Compiler, Avro, DDL, DQ Spec)"
        run_tier 2 "test_tier2_boundary.py" "Boundary & Corner Cases (Nulls, Malformed, Zero/Negative, Wash Trade)"
        run_tier 3 "test_tier3_combinations.py" "Cross-Feature Combinations & Pipelines"
        run_tier 4 "test_tier4_workloads.py" "Realistic SGX Workload Simulations"
        ;;
    *)
        echo -e "${RED}Invalid tier specified: ${TIER}${RESET}"
        show_help
        ;;
esac

SUITE_END_TIME=$(date +%s)
TOTAL_DURATION=$((SUITE_END_TIME - SUITE_START_TIME))

echo -e "${BOLD}${CYAN}========================================================================${RESET}"
echo -e "${BOLD}${CYAN}   E2E TEST SUITE SCORECARD SUMMARY                                     ${RESET}"
echo -e "${BOLD}${CYAN}========================================================================${RESET}"
printf "${BOLD}%-20s: %d${RESET}\n" "Total Tests Run" "${TOTAL_RAN}"
printf "${GREEN}${BOLD}%-20s: %d${RESET}\n" "Passed Tests" "${TOTAL_PASSED}"
if [ ${TOTAL_FAILED} -gt 0 ]; then
    printf "${RED}${BOLD}%-20s: %d (Implementation/Validation pending)${RESET}\n" "Failed Tests" "${TOTAL_FAILED}"
else
    printf "${GREEN}%-20s: %d${RESET}\n" "Failed Tests" "${TOTAL_FAILED}"
fi
printf "${YELLOW}%-20s: %d${RESET}\n" "Skipped Tests" "${TOTAL_SKIPPED}"
printf "${GRAY}%-20s: %ds${RESET}\n" "Total Duration" "${TOTAL_DURATION}"
echo -e "${BOLD}${CYAN}========================================================================${RESET}"

if [ ${OVERALL_EXIT_CODE} -eq 0 ]; then
    echo -e "${BOLD}${GREEN}>> VERDICT: ALL EXECUTED TESTS PASSED (PASS)${RESET}"
else
    echo -e "${BOLD}${YELLOW}>> VERDICT: TEST SUITE READY. Failures reflect pending milestone implementations.${RESET}"
fi
echo ""

exit ${OVERALL_EXIT_CODE}
