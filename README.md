# Docker Volume Backup System

A comprehensive Flask-based web application for backing up and restoring Docker volumes using Restic and Rclone. Designed for easy deployment on CapRover with support for various remote storage backends including OneDrive.

## Features

- **Web Dashboard**: Intuitive interface for managing backups and volumes
- **HTTP Basic Authentication**: Optional security for web interface
- **Volume Discovery**: Automatically detects mounted Docker volumes
- **Restic Integration**: Deduplicated, incremental backups with encryption
- **Rclone Support**: Compatible with 40+ cloud storage providers
- **Configurable Scheduling**: Web-based cron schedule editor
- **Manual Operations**: On-demand backup and restore functionality
- **Real-time Monitoring**: Live status updates and progress tracking
- **Enhanced Progress Tracking**: ETA calculations and detailed status indicators
- **Comprehensive Logging**: Detailed logs for troubleshooting
- **Download Capabilities**: Download logs and backup archives
- **Rclone Config Editor**: Advanced configuration management

## Quick Start with CapRover

### 1. Deploy the Application

1. **Create a new app in CapRover**:
   - Go to your CapRover dashboard
   - Click "Create New App"
   - Enter app name (e.g., `volume-backup`)

2. **Deploy from GitHub**:
   - Go to the "Deployment" tab
   - Select "Deploy from Github/Bitbucket/Gitlab"
   - Enter this repository URL
   - Choose branch (main)
   - Click "Deploy Now"

### 2. Configure Environment Variables

In CapRover's App Config, set the following environment variables:

```bash
# Required - Restic repository password
RESTIC_PASSWORD=your-secure-password-here

# Required - Rclone remote name (configured via rclone config)
RCLONE_REMOTE=onedrive

# Required - Folder path in remote storage
RCLONE_FOLDER=docker-backups

# Optional - Timezone
TZ=America/New_York

# Optional - Basic authentication (recommended for production)
AUTH_USER=admin
AUTH_PASSWORD=secure-password
```

### 3. Configure Persistent Directories

In CapRover's App Config, add these persistent directories:

```
/data -> /data
```

### 4. Mount Docker Volumes

To backup specific volumes, add them as volume mappings:

```
volume1 -> /volumes/volume1:ro
volume2 -> /volumes/volume2:ro
```

Example for common applications:
```
wordpress_wp-content -> /volumes/wordpress:ro
nextcloud_data -> /volumes/nextcloud:ro
postgres_data -> /volumes/postgres:ro
```

### 5. Enable HTTPS and Configure Domain

1. Go to "HTTP Settings" in CapRover
2. Enable HTTPS
3. Set up your domain (e.g., `backup.yourdomain.com`)

## Initial Setup

### 1. Configure Rclone

After deployment, you need to configure rclone for your storage backend:

1. **Access the container shell**:
   ```bash
   docker exec -it $(docker ps | grep volume-backup | awk '{print $1}') /bin/bash
   ```

2. **Run rclone configuration**:
   ```bash
   rclone config
   ```

3. **For OneDrive setup**:
   - Choose "New remote"
   - Enter name: `onedrive`
   - Choose "Microsoft OneDrive"
   - Follow the authentication prompts
   - Choose "OneDrive Personal" or "OneDrive Business" as needed

4. **Test the configuration**:
   ```bash
   rclone lsd onedrive:
   ```

### 2. Access the Web Interface

1. Open your configured domain in a browser
2. Log in with your credentials (if authentication is enabled)
3. Go to "Volumes" tab to select which volumes to backup
4. Click "Save Selection"
5. Configure backup schedule in "Config" tab if needed
6. Return to "Dashboard" and click "Start Backup Now"

## Docker Compose Example

For manual deployment with Docker Compose:

```yaml
version: '3.8'

services:
  volume-backup:
    image: ghcr.io/yourusername/docker-volume-backup:latest
    container_name: volume-backup
    ports:
      - "5000:5000"
    environment:
      - RESTIC_PASSWORD=your-secure-password
      - RCLONE_REMOTE=onedrive
      - RCLONE_FOLDER=docker-backups
      - TZ=America/New_York
      - AUTH_USER=admin
      - AUTH_PASSWORD=secure-password
    volumes:
      # Persistent data
      - ./backup-data:/data
      
      # Mount volumes to backup (read-only)
      - wordpress_wp-content:/volumes/wordpress:ro
      - nextcloud_data:/volumes/nextcloud:ro
      - postgres_data:/volumes/postgres:ro
    restart: unless-stopped

volumes:
  wordpress_wp-content:
    external: true
  nextcloud_data:
    external: true
  postgres_data:
    external: true
```

## Configuration Options

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `RESTIC_PASSWORD` | Yes | - | Password for restic repository encryption |
| `RCLONE_REMOTE` | Yes | - | Name of configured rclone remote |
| `RCLONE_FOLDER` | Yes | - | Folder path in remote storage |
| `TZ` | No | UTC | Timezone for scheduling |
| `AUTH_USER` | No | - | Username for HTTP basic auth |
| `AUTH_PASSWORD` | No | - | Password for HTTP basic auth |
| `SECRET_KEY` | No | auto | Flask secret key for sessions |

### Backup Schedule Configuration

The backup schedule can be configured through the web interface using standard cron syntax:

| Field | Description | Example |
|-------|-------------|---------|
| Minute | 0-59 | 0 (top of hour) |
| Hour | 0-23 | 2 (2 AM) |
| Day | 1-31 or * | * (every day) |
| Month | 1-12 or * | * (every month) |
| Day of Week | 0-7 or * | * (every day) |

**Common Examples**:
- Daily at 2 AM: `0 2 * * *`
- Every 6 hours: `0 */6 * * *`
- Weekly on Sunday at 3 AM: `0 3 * * 0`
- Monthly on 1st at midnight: `0 0 1 * *`

### Volume Mounts

| Mount Point | Purpose | Example |
|-------------|---------|---------|
| `/data` | Persistent storage for config, logs, cache | `./backup-data:/data` |
| `/volumes/<name>` | Docker volumes to backup | `volume_name:/volumes/volume_name:ro` |

## Usage

### Web Interface

1. **Dashboard**: Overview of backup status, schedule, and quick actions
2. **Volumes**: Select which mounted volumes to include in backups
3. **Backups**: View backup history and restore specific snapshots
4. **Config**: Manage settings, backup schedule, and rclone configuration
5. **Logs**: Monitor application logs and troubleshoot issues

### Backup Operations

- **Automatic**: Configurable schedule via web interface
- **Manual**: Click "Start Backup Now" in the web interface
- **Selective**: Only backup volumes you've selected

### Restore Operations

1. Go to "Backups" tab
2. Find the snapshot you want to restore
3. Click "Restore" button
4. Specify target path (default: `/data/restore`)
5. Monitor progress in real-time

### Download Features

- **Download Logs**: Get all application logs as a zip file
- **Download Backups**: Download specific backup snapshots as tar.gz archives
- **Export Configuration**: Backup your settings and rclone configuration

### Monitoring

- Real-time status updates during operations
- Enhanced progress tracking with ETA calculations
- Comprehensive logging with different levels (INFO, WARNING, ERROR)
- Detailed progress indicators with visual feedback
- System resource monitoring

## Advanced Configuration

### Backup Schedule Management

The backup schedule can be managed through the web interface:

1. Go to "Config" tab
2. Modify the schedule fields using cron syntax
3. Click "Save Schedule"
4. Changes take effect immediately

### Rclone Configuration Management

**Basic Setup** (Recommended):
1. Access container shell: `docker exec -it volume-backup /bin/bash`
2. Run: `rclone config`
3. Follow interactive setup

**Advanced Setup** (Web Interface):
1. Go to "Config" tab
2. Click "Edit Config" under Rclone Configuration
3. Directly edit the rclone.conf file
4. Click "Save" to apply changes
5. Use "Test Connection" to verify

### Multiple Storage Backends

Configure additional rclone remotes for redundancy:

```bash
rclone config  # Add second remote
```

Then modify environment variables or create custom backup scripts.

### Custom Retention Policies

Restic supports flexible retention policies. Modify the backup script to include:

```bash
restic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 12 --prune
```

## Troubleshooting

### Common Issues

**1. "No volumes found"**
- Ensure volumes are mounted to `/volumes/*` with read permissions
- Check CapRover volume mappings
- Verify volume names don't contain spaces or special characters

**2. "RESTIC_PASSWORD not set"**
- Verify environment variable is configured in CapRover
- Restart the application after setting variables

**3. "Rclone authentication failed"**
- Re-run `rclone config` to set up authentication
- Check if tokens have expired (common with OneDrive)
- Verify RCLONE_REMOTE matches the configured remote name
- Use the web interface to test the connection

**4. "Backup fails with permission errors"**
- Ensure volumes are mounted read-only (`:ro`)
- Check if the backup user has access to volume data

**5. "Schedule not working"**
- Check if cron daemon is running in the container
- Verify schedule syntax using online cron validators
- Check cron logs: `/data/cron.log`

### Log Analysis

Check logs through the web interface or directly:

```bash
# Application logs
docker exec volume-backup tail -f /data/app.log

# Cron logs
docker exec volume-backup tail -f /data/cron.log

# Container logs
docker logs volume-backup -f
```

### Testing Configuration

Use the built-in test features:

1. **Test Rclone**: Go to Config page and click "Test Connection"
2. **Test Backup**: Select a single small volume and run a manual backup
3. **Test Restore**: Restore a backup to a test directory
4. **Download Test**: Download logs to verify file access

## Security Considerations

1. **Use Strong Passwords**: Set secure values for `RESTIC_PASSWORD` and `AUTH_PASSWORD`
2. **Enable HTTPS**: Always use HTTPS in production with CapRover
3. **Enable Authentication**: Set `AUTH_USER` and `AUTH_PASSWORD` for production
3. **Network Security**: Consider restricting access to the backup interface
4. **Volume Permissions**: Mount volumes as read-only when possible
5. **Regular Updates**: Keep the container image updated for security patches
6. **Secure Rclone Config**: Protect rclone configuration with appropriate permissions

## Backup Best Practices

1. **Test Restores**: Regularly test restore procedures
2. **Download Backups**: Periodically download backup archives for offline storage
2. **Monitor Storage**: Check available space on remote storage
3. **Verify Backups**: Use restic's check command periodically
4. **Document Recovery**: Keep restore procedures documented
5. **Multiple Backends**: Consider using multiple storage backends for redundancy
6. **Schedule Optimization**: Adjust backup frequency based on data change rate

## Updates and Maintenance

### Updating the Application

In CapRover:
1. Go to your app's Deployment tab
2. Click "Deploy Now" to pull the latest image
3. Monitor the deployment logs

### Database Migration

Configuration is stored in JSON format and automatically migrated between versions.

### Backup Verification

Regular verification is recommended:

```bash
# Inside container
restic check
restic check --read-data
```

## Support and Contributing

- **Issues**: Report bugs or request features via GitHub Issues
- **Documentation**: Contribute to documentation improvements
- **Code**: Submit pull requests for enhancements

## License

MIT License - see LICENSE file for details.

---

For additional help or advanced configurations, refer to the official documentation for [Restic](https://restic.readthedocs.io/) and [Rclone](https://rclone.org/docs/).