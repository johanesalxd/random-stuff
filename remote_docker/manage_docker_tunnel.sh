#!/bin/bash
#
# Manage Docker SSH tunnel connection.

# Tunnel configuration
readonly LOCAL_PORT=2375
readonly REMOTE_PORT=2375

#######################################
# Start the Docker SSH tunnel.
# Globals:
#   LOCAL_PORT
#   REMOTE_PORT
# Arguments:
#   $1 - Remote host (user@hostname)
# Outputs:
#   Writes status messages to stdout
#######################################
start_tunnel() {
  local remote_host="$1"

  if [[ -z "${remote_host}" ]]; then
    echo "Error: Remote host is required"
    echo "Usage: $(basename "$0") start <user@hostname>"
    return 1
  fi

  if lsof -i ":${LOCAL_PORT}" > /dev/null 2>&1; then
    echo "Tunnel already running on port ${LOCAL_PORT}"
    return 0
  fi

  echo "Starting Docker SSH tunnel to ${remote_host}..."
  ssh -f -N "${remote_host}" -L "${LOCAL_PORT}:localhost:${REMOTE_PORT}"

  if [[ $? -eq 0 ]]; then
    echo "Tunnel started successfully"
    echo "Remote host: ${remote_host}"
    echo "Docker host: tcp://localhost:${LOCAL_PORT}"
  else
    echo "Failed to start tunnel"
    return 1
  fi
}

#######################################
# Stop the Docker SSH tunnel.
# Globals:
#   LOCAL_PORT
# Arguments:
#   None
# Outputs:
#   Writes status messages to stdout
#######################################
stop_tunnel() {
  echo "Stopping Docker SSH tunnel..."

  # Kill any SSH tunnel using the local port
  pkill -f "ssh.*-L ${LOCAL_PORT}:localhost:${REMOTE_PORT}"

  if [[ $? -eq 0 ]]; then
    echo "Tunnel stopped"
  else
    echo "No tunnel to stop"
  fi
}

#######################################
# Check status of Docker SSH tunnel.
# Globals:
#   LOCAL_PORT
# Arguments:
#   None
# Outputs:
#   Writes tunnel status to stdout
#######################################
check_status() {
  echo "=== Docker SSH Tunnel Status ==="

  if lsof -i ":${LOCAL_PORT}" > /dev/null 2>&1; then
    echo "Tunnel is active on port ${LOCAL_PORT}"
    echo ""
    echo "Active connections:"
    lsof -i ":${LOCAL_PORT}"
  else
    echo "Tunnel is not running"
  fi
}

#######################################
# Restart the Docker SSH tunnel.
# Globals:
#   None
# Arguments:
#   $1 - Remote host (user@hostname)
# Outputs:
#   Writes status messages to stdout
#######################################
restart_tunnel() {
  local remote_host="$1"

  if [[ -z "${remote_host}" ]]; then
    echo "Error: Remote host is required"
    echo "Usage: $(basename "$0") restart <user@hostname>"
    return 1
  fi

  echo "Restarting Docker SSH tunnel..."
  stop_tunnel
  sleep 1
  start_tunnel "${remote_host}"
}

#######################################
# Display usage information.
# Globals:
#   LOCAL_PORT
#   REMOTE_PORT
# Arguments:
#   None
# Outputs:
#   Writes usage information to stdout
#######################################
show_usage() {
  cat << EOF
Usage: $(basename "$0") {start|stop|status|restart} [remote-host]

Commands:
  start <user@hostname>   - Start the Docker SSH tunnel
  stop                    - Stop the Docker SSH tunnel
  status                  - Check if tunnel is running
  restart <user@hostname> - Restart the Docker SSH tunnel

Configuration:
  Local Port:  ${LOCAL_PORT}
  Remote Port: ${REMOTE_PORT}

Examples:
  $(basename "$0") start user@example.com
  $(basename "$0") status
  $(basename "$0") stop
  $(basename "$0") restart user@example.com
EOF
}

#######################################
# Main function to handle command-line arguments.
# Globals:
#   None
# Arguments:
#   $1 - Command to execute (start|stop|status|restart)
#   $2 - Remote host (required for start and restart)
# Outputs:
#   Writes command results to stdout
#######################################
main() {
  if [[ $# -eq 0 ]]; then
    show_usage
    exit 1
  fi

  local command="$1"
  local remote_host="$2"

  case "${command}" in
    start)
      start_tunnel "${remote_host}"
      ;;
    stop)
      stop_tunnel
      ;;
    status)
      check_status
      ;;
    restart)
      restart_tunnel "${remote_host}"
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
