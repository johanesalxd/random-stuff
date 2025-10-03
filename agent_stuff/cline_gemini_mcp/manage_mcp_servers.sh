#!/bin/bash
#
# Manage BigQuery Toolbox MCP servers for Cline.

# Server configuration
readonly CONVERSATIONAL_TOOLBOX="${HOME}/.gemini/extensions/bigquery-conversational-analytics/toolbox"
readonly CONVERSATIONAL_TOOLS="${HOME}/.gemini/extensions/bigquery-conversational-analytics/tools.yaml"
readonly CONVERSATIONAL_PORT=5001
readonly CONVERSATIONAL_LOG="/tmp/toolbox-conversational.log"

readonly DATA_ANALYTICS_TOOLBOX="${HOME}/.gemini/extensions/bigquery-data-analytics/toolbox"
readonly DATA_ANALYTICS_TOOLS="${HOME}/.gemini/extensions/bigquery-data-analytics/tools.yaml"
readonly DATA_ANALYTICS_PORT=5002
readonly DATA_ANALYTICS_LOG="/tmp/toolbox-data-analytics.log"

#######################################
# Start both MCP servers.
# Globals:
#   CONVERSATIONAL_TOOLBOX
#   CONVERSATIONAL_TOOLS
#   CONVERSATIONAL_PORT
#   CONVERSATIONAL_LOG
#   DATA_ANALYTICS_TOOLBOX
#   DATA_ANALYTICS_TOOLS
#   DATA_ANALYTICS_PORT
#   DATA_ANALYTICS_LOG
# Arguments:
#   None
# Outputs:
#   Writes status messages to stdout
#######################################
start_servers() {
  echo "Starting BigQuery MCP servers..."

  # Start conversational analytics server
  nohup "${CONVERSATIONAL_TOOLBOX}" \
    --tools-file "${CONVERSATIONAL_TOOLS}" \
    --port "${CONVERSATIONAL_PORT}" \
    > "${CONVERSATIONAL_LOG}" 2>&1 &

  echo "Started bigquery-conversational-analytics on port ${CONVERSATIONAL_PORT}"

  # Start data analytics server
  nohup "${DATA_ANALYTICS_TOOLBOX}" \
    --tools-file "${DATA_ANALYTICS_TOOLS}" \
    --port "${DATA_ANALYTICS_PORT}" \
    > "${DATA_ANALYTICS_LOG}" 2>&1 &

  echo "Started bigquery-data-analytics on port ${DATA_ANALYTICS_PORT}"

  # Wait for servers to initialize
  sleep 2

  echo "Servers started. Use 'status' command to verify."
}

#######################################
# Stop Cline's MCP servers only.
# This function only stops servers running with --port flag,
# preserving Gemini CLI's --stdio servers.
# Globals:
#   CONVERSATIONAL_PORT
#   DATA_ANALYTICS_PORT
# Arguments:
#   None
# Outputs:
#   Writes status messages to stdout
#######################################
stop_servers() {
  echo "Stopping Cline MCP servers (HTTP/SSE only)..."

  # Only kill toolbox processes with --port flag (Cline's servers)
  # This preserves Gemini CLI's --stdio processes
  pkill -f "toolbox.*--port ${CONVERSATIONAL_PORT}"
  pkill -f "toolbox.*--port ${DATA_ANALYTICS_PORT}"

  echo "Cline MCP servers stopped. Gemini CLI servers preserved."
}

#######################################
# Check status of MCP servers.
# Displays both Cline's HTTP/SSE servers and Gemini CLI's STDIO servers.
# Globals:
#   None
# Arguments:
#   None
# Outputs:
#   Writes server status to stdout
#######################################
check_status() {
  echo "=== Cline MCP Servers (HTTP/SSE) ==="
  local cline_servers
  cline_servers=$(ps -ef | grep "toolbox.*--port" | grep -v grep)

  if [[ -z "${cline_servers}" ]]; then
    echo "No Cline MCP servers running."
  else
    echo "${cline_servers}"
  fi

  echo ""
  echo "=== Gemini CLI Servers (STDIO) ==="
  local gemini_servers
  gemini_servers=$(ps -ef | grep "toolbox.*--stdio" | grep -v grep)

  if [[ -z "${gemini_servers}" ]]; then
    echo "No Gemini CLI servers running."
  else
    echo "${gemini_servers}"
  fi
}

#######################################
# Display recent logs from both servers.
# Globals:
#   CONVERSATIONAL_LOG
#   DATA_ANALYTICS_LOG
# Arguments:
#   None
# Outputs:
#   Writes log contents to stdout
#######################################
view_logs() {
  echo "=== Conversational Analytics Logs ==="
  if [[ -f "${CONVERSATIONAL_LOG}" ]]; then
    tail -20 "${CONVERSATIONAL_LOG}"
  else
    echo "Log file not found: ${CONVERSATIONAL_LOG}"
  fi

  echo ""
  echo "=== Data Analytics Logs ==="
  if [[ -f "${DATA_ANALYTICS_LOG}" ]]; then
    tail -20 "${DATA_ANALYTICS_LOG}"
  else
    echo "Log file not found: ${DATA_ANALYTICS_LOG}"
  fi
}

#######################################
# Display usage information.
# Globals:
#   None
# Arguments:
#   None
# Outputs:
#   Writes usage information to stdout
#######################################
show_usage() {
  cat << EOF
Usage: $(basename "$0") {start|stop|status|logs}

Commands:
  start   - Start both MCP servers
  stop    - Stop all MCP servers
  status  - Check if servers are running
  logs    - View recent server logs

Examples:
  $(basename "$0") start
  $(basename "$0") status
EOF
}

#######################################
# Main function to handle command-line arguments.
# Globals:
#   None
# Arguments:
#   Command to execute (start|stop|status|logs)
# Outputs:
#   Writes command results to stdout
#######################################
main() {
  if [[ $# -eq 0 ]]; then
    show_usage
    exit 1
  fi

  local command="$1"

  case "${command}" in
    start)
      start_servers
      ;;
    stop)
      stop_servers
      ;;
    status)
      check_status
      ;;
    logs)
      view_logs
      ;;
    *)
      echo "Error: Unknown command '${command}'"
      echo ""
      show_usage
      exit 1
      ;;
  esac
}

main "$@"
