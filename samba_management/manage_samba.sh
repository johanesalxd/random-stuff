#!/bin/bash
#
# Manage Samba services (smbd and nmbd) manually without LaunchDaemon.

# Samba configuration
readonly SMBD="/opt/homebrew/sbin/samba-dot-org-smbd"
readonly NMBD="/opt/homebrew/sbin/nmbd"
readonly CONFIG="/opt/homebrew/etc/samba/smb.conf"
readonly LOG_DIR="/var/log/samba"
readonly PDBEDIT="/opt/homebrew/bin/pdbedit"

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
# Ensure required Samba directories exist.
# Creates the private directory needed for IPC communication.
# Globals:
#   SMBD
# Arguments:
#   None
# Outputs:
#   Writes status messages to stdout if directories are created
# Returns:
#   0 on success, 1 on failure
#######################################
ensure_directories() {
  local real_smbd
  local samba_base
  local private_dir

  # Resolve symlink to get actual Cellar path
  real_smbd=$(readlink -f "${SMBD}" 2>/dev/null || realpath "${SMBD}" 2>/dev/null)
  if [[ -z "${real_smbd}" ]]; then
    echo "ERROR: Could not resolve path for ${SMBD}"
    return 1
  fi

  # Get the Cellar base directory (e.g., /opt/homebrew/Cellar/samba/4.23.4)
  samba_base=$(dirname "$(dirname "${real_smbd}")")
  private_dir="${samba_base}/private"

  if [[ ! -d "${private_dir}" ]]; then
    echo "Creating missing directory: ${private_dir}"
    if sudo mkdir -p "${private_dir}"; then
      echo "Directory created successfully"
    else
      echo "ERROR: Failed to create directory: ${private_dir}"
      return 1
    fi
  fi

  return 0
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

  if ! ensure_directories; then
    echo "Failed to ensure required directories exist"
    return 1
  fi

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
# Check Samba user database and display instructions.
# Globals:
#   PDBEDIT
# Arguments:
#   None
# Outputs:
#   Writes user information and instructions to stdout
#######################################
check_users() {
  echo "=== Checking Samba User Database ==="
  echo ""

  if [[ ! -x "${PDBEDIT}" ]]; then
    echo "ERROR: pdbedit not found at ${PDBEDIT}"
    return 1
  fi

  echo "Current Samba users:"
  sudo "${PDBEDIT}" -L 2>&1

  echo ""
  echo "=== System Users (pi and johanesalxd) ==="
  dscl . -list /Users | grep -E "^(pi|johanesalxd)$"

  echo ""
  echo "To add a user to Samba, run:"
  echo "  sudo smbpasswd -a <username>"
  echo ""
  echo "Example:"
  echo "  sudo smbpasswd -a pi"
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
Usage: $(basename "$0") {start|stop|restart|status|logs|users}

Commands:
  start   - Start smbd and nmbd services
  stop    - Stop smbd and nmbd services
  restart - Restart both services
  status  - Check if services are running
  logs    - View recent server logs
  users   - Check Samba user database and show instructions

Examples:
  $(basename "$0") start
  $(basename "$0") status
  $(basename "$0") users
EOF
}

#######################################
# Main function to handle command-line arguments.
# Globals:
#   None
# Arguments:
#   Command to execute (start|stop|restart|status|logs|users)
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
    users)
      check_users
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
