# Docker SSH Tunnel Management

Manage Docker SSH tunnel connection to remote host.

## Configuration

The tunnel is configured with:
- Local Port: `2375`
- Remote Port: `2375`
- Remote Host: Specified as command-line argument

## Usage

```bash
manage-docker {start|stop|status|restart} [remote-host]
```

### Commands

- `start <user@hostname>` - Start the Docker SSH tunnel to specified remote host
- `stop` - Stop the Docker SSH tunnel
- `status` - Check if tunnel is running
- `restart <user@hostname>` - Restart the Docker SSH tunnel to specified remote host

### Examples

```bash
# Start the tunnel to a remote host
manage-docker start user@remote-host

# Check tunnel status
manage-docker status

# Stop the tunnel
manage-docker stop

# Restart the tunnel to a remote host
manage-docker restart user@remote-host
```

## Environment Variable

The `.zshrc` file sets the Docker host environment variable:

```bash
export DOCKER_HOST=tcp://localhost:2375
```

This allows Docker commands to automatically use the tunneled connection.
