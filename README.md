# Docker Volume Backup System

A comprehensive Flask-based web application for backing up and restoring Docker volumes using Restic and Rclone. Designed for easy deployment on CapRover with support for various remote storage backends including OneDrive.

## Features

- **Web Dashboard**: Intuitive interface for managing backups and volumes
- **Volume Discovery**: Automatically detects mounted Docker volumes
- **Restic Integration**: Deduplicated, incremental backups with encryption
- **Rclone Support**: Compatible with 40+ cloud storage providers
- **Scheduled Backups**: Automated daily backups via cron
- **Manual Operations**: On-demand backup and restore functionality
- **Real-time Monitoring**: Live status updates and progress tracking
- **Comprehensive Logging**: Detailed logs for troubleshooting
- **Basic Authentication**: Optional HTTP authentication for security

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

# Optional - Basic authentication
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
5. Return to "Dashboard" and click "Start Backup Now"

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
4. **Config**: Manage settings and view system information
5. **Logs**: Monitor application logs and troubleshoot issues

### Backup Operations

- **Automatic**: Daily at 2:00 AM (configurable via cron)
- **Manual**: Click "Start Backup Now" in the web interface
- **Selective**: Only backup volumes you've selected

### Restore Operations

1. Go to "Backups" tab
2. Find the snapshot you want to restore
3. Click "Restore" button
4. Specify target path (default: `/data/restore`)
5. Monitor progress in real-time

### Monitoring

- Real-time status updates during operations
- Comprehensive logging with different levels (INFO, WARNING, ERROR)
- Progress tracking with percentage completion
- Email notifications (if configured)

## Advanced Configuration

### Custom Backup Schedule

To modify the backup schedule, edit the cron job in the container:

```bash
# Access container
docker exec -it volume-backup /bin/bash

# Edit crontab
crontab -e

# Example: Backup every 6 hours
0 */6 * * * cd /app && python cron_backup.py >> /data/cron.log 2>&1
```

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

**4. "Backup fails with permission errors"**
- Ensure volumes are mounted read-only (`:ro`)
- Check if the backup user has access to volume data

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

1. **Test Rclone**: Go to Config page and click "Test Rclone Connection"
2. **Test Backup**: Select a single small volume and run a manual backup
3. **Test Restore**: Restore a backup to a test directory

## Security Considerations

1. **Use Strong Passwords**: Set secure values for `RESTIC_PASSWORD` and `AUTH_PASSWORD`
2. **Enable HTTPS**: Always use HTTPS in production with CapRover
3. **Network Security**: Consider restricting access to the backup interface
4. **Volume Permissions**: Mount volumes as read-only when possible
5. **Regular Updates**: Keep the container image updated for security patches

## Backup Best Practices

1. **Test Restores**: Regularly test restore procedures
2. **Monitor Storage**: Check available space on remote storage
3. **Verify Backups**: Use restic's check command periodically
4. **Document Recovery**: Keep restore procedures documented
5. **Multiple Backends**: Consider using multiple storage backends for redundancy

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