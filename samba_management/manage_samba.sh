#!/bin/bash
#
# Manage Samba services (smbd and nmbd) manually without LaunchDaemon.

# Samba configuration
readonly SMBD="/opt/homebrew/sbin/samba-dot-org-smbd"
readonly NMBD="/opt/homebrew/sbin/nmbd"
readonly CONFIG="/opt/homebrew/etc/samba/smb.conf"
readonly LOG_DIR="/var/log/samba"

#######################################
# Check if a process is running.
# Globals:
#   None
# Arguments:
#   Process name to check
# Outputs:
#   None
# Returns:
#   0 if process is running, 1 otherwise
#######################################
is_running() {
  local process="$1"
  pgrep -f "${process}" > /dev/null 2>&1
}

#######################################
# Start Samba services (smbd and nmbd).
# Globals:
#   SMBD
#   NMBD
#   CONFIG
# Arguments:
#   None
# Outputs:
#   Writes status messages to stdout
#######################################
start_samba() {
  echo "Starting Samba services..."

  if is_running "samba-dot-org-smbd"; then
    echo "smbd is already running"
  else
    echo "Starting smbd..."
    sudo "${SMBD}" -D -s "${CONFIG}"
    sleep 2
    if is_running "samba-dot-org-smbd"; then
      echo "smbd started successfully"
    else
      echo "Failed to start smbd"
    fi
  fi

  if is_running "nmbd"; then
    echo "nmbd is already running"
  else
    echo "Starting nmbd..."
    sudo "${NMBD}" -D -s "${CONFIG}"
    sleep 2
    if is_running "nmbd"; then
      echo "nmbd started successfully"
    else
      echo "Failed to start nmbd"
    fi
  fi

  echo ""
  check_status
}

#######################################
# Stop Samba services (smbd and nmbd).
# Globals:
#   None
# Arguments:
#   None
# Outputs:
#   Writes status messages to stdout
#######################################
stop_samba() {
  echo "Stopping Samba services..."

  if is_running "samba-dot-org-smbd"; then
    echo "Stopping smbd..."
    sudo killall samba-dot-org-smbd 2>/dev/null
    sleep 1
    echo "smbd stopped"
  else
    echo "smbd is not running"
  fi

  if is_running "nmbd"; then
    echo "Stopping nmbd..."
    sudo killall nmbd 2>/dev/null
    sleep 1
    echo "nmbd stopped"
  else
    echo "nmbd is not running"
  fi
}

#######################################
# Restart Samba services.
# Globals:
#   None
# Arguments:
#   None
# Outputs:
#   Writes status messages to stdout
#######################################
restart_samba() {
  echo "Restarting Samba services..."
  stop_samba
  sleep 2
  start_samba
}

#######################################
# Check status of Samba services.
# Displays process counts and warns if nmbd has too many processes.
# Globals:
#   None
# Arguments:
#   None
# Outputs:
#   Writes service status to stdout
#######################################
check_status() {
  echo "=== Samba Service Status ==="

  if is_running "samba-dot-org-smbd"; then
    local smbd_count
    smbd_count=$(pgrep -f "samba-dot-org-smbd" | wc -l | tr -d ' ')
    echo "smbd:  RUNNING (${smbd_count} processes)"
  else
    echo "smbd:  STOPPED"
  fi

  if is_running "nmbd"; then
    local nmbd_count
    nmbd_count=$(pgrep -f "nmbd" | wc -l | tr -d ' ')
    echo "nmbd:  RUNNING (${nmbd_count} processes)"

    if [[ "${nmbd_count}" -gt 10 ]]; then
      echo "WARNING: Too many nmbd processes detected"
      echo "Consider restarting: manage-samba restart"
    fi
  else
    echo "nmbd:  STOPPED"
  fi

  if is_running "samba-dot-org-smbd"; then
    echo ""
    echo "Access your share at:"
    echo "  smb://jos-mac-mini/sambashare"
    local ip_addr
    ip_addr=$(ipconfig getifaddr en0 2>/dev/null)
    if [[ -n "${ip_addr}" ]]; then
      echo "  smb://${ip_addr}/sambashare"
    fi
  fi
}

#######################################
# Display recent logs from both services.
# Globals:
#   LOG_DIR
# Arguments:
#   None
# Outputs:
#   Writes log contents to stdout
#######################################
view_logs() {
  echo "=== Samba Service Logs ==="

  if [[ -f "${LOG_DIR}/log.smbd" ]]; then
    echo ""
    echo "smbd log (last 20 lines):"
    tail -20 "${LOG_DIR}/log.smbd"
  else
    echo "smbd log file not found: ${LOG_DIR}/log.smbd"
  fi

  if [[ -f "${LOG_DIR}/log.nmbd" ]]; then
    echo ""
    echo "nmbd log (last 20 lines):"
    tail -20 "${LOG_DIR}/log.nmbd"
  else
    echo "nmbd log file not found: ${LOG_DIR}/log.nmbd"
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
Usage: $(basename "$0") {start|stop|restart|status|logs}

Commands:
  start   - Start smbd and nmbd services
  stop    - Stop smbd and nmbd services
  restart - Restart both services
  status  - Check if services are running
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
#   Command to execute (start|stop|restart|status|logs)
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
      start_samba
      ;;
    stop)
      stop_samba
      ;;
    restart)
      restart_samba
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
