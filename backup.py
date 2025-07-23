import os
import json
import subprocess
import threading
import time
import re
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class BackupStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"

class BackupEngine:
    def __init__(self):
        self.status = BackupStatus.IDLE
        self.current_operation = None
        self.progress = 0
        self.message = ""
        self.logs = []
        self.lock = threading.Lock()
        
        # Ensure restic repository is initialized
        self._init_repository()
    
    def _init_repository(self):
        """Initialize restic repository if it doesn't exist"""
        try:
            env = self._get_env_vars()
            if not env.get('RESTIC_PASSWORD'):
                logger.warning("RESTIC_PASSWORD not set")
                return
            
            # Check if repository exists
            result = subprocess.run([
                'restic', 'snapshots'
            ], env=env, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                # Repository doesn't exist, initialize it
                logger.info("Initializing restic repository")
                result = subprocess.run([
                    'restic', 'init'
                ], env=env, capture_output=True, text=True, timeout=60)
                
                if result.returncode == 0:
                    logger.info("Repository initialized successfully")
                else:
                    logger.error(f"Failed to initialize repository: {result.stderr}")
            
        except Exception as e:
            logger.error(f"Error initializing repository: {e}")
    
    def _get_env_vars(self):
        """Get environment variables for restic/rclone"""
        env = os.environ.copy()
        env['RCLONE_CONFIG'] = '/data/rclone.conf'
        env['RESTIC_REPOSITORY'] = f"rclone:{env.get('RCLONE_REMOTE', 'onedrive')}:{env.get('RCLONE_FOLDER', 'backup')}"
        return env
    
    def _log_message(self, level, message):
        """Add a log message"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'message': message
        }
        
        with self.lock:
            self.logs.append(log_entry)
            # Keep only last 1000 log entries
            if len(self.logs) > 1000:
                self.logs = self.logs[-1000:]
        
        # Also log to Python logger
        if level == 'ERROR':
            logger.error(message)
        elif level == 'WARNING':
            logger.warning(message)
        else:
            logger.info(message)
    
    def get_status(self):
        """Get current status"""
        with self.lock:
            status = {
                'status': self.status.value,
                'operation': self.current_operation,
                'progress': self.progress,
                'message': self.message,
                'start_time': getattr(self, 'start_time', None),
                'estimated_completion': getattr(self, 'estimated_completion', None)
            }
            
            # Calculate estimated completion time
            if self.status == BackupStatus.RUNNING and hasattr(self, 'start_time') and self.progress > 0:
                elapsed = time.time() - self.start_time
                if self.progress > 5:  # Only estimate after some progress
                    total_estimated = elapsed * (100 / self.progress)
                    remaining = total_estimated - elapsed
                    status['estimated_completion'] = time.time() + remaining
            
            return status
    
    def get_recent_logs(self, limit=50):
        """Get recent log entries"""
        with self.lock:
            return self.logs[-limit:] if self.logs else []
    
    def list_snapshots(self):
        """List all backup snapshots"""
        try:
            env = self._get_env_vars()
            result = subprocess.run([
                'restic', 'snapshots', '--json'
            ], env=env, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                snapshots = json.loads(result.stdout)
                # Format snapshots for display
                formatted_snapshots = []
                for snapshot in snapshots:
                    formatted_snapshots.append({
                        'id': snapshot.get('short_id', snapshot.get('id', 'Unknown')),
                        'time': snapshot.get('time', 'Unknown'),
                        'hostname': snapshot.get('hostname', 'Unknown'),
                        'paths': snapshot.get('paths', []),
                        'tags': snapshot.get('tags', [])
                    })
                return formatted_snapshots
            else:
                self._log_message('ERROR', f"Failed to list snapshots: {result.stderr}")
                return []
        except Exception as e:
            self._log_message('ERROR', f"Error listing snapshots: {e}")
            return []
    
    def run_backup(self, selected_volumes):
        """Run backup for selected volumes"""
        with self.lock:
            if self.status == BackupStatus.RUNNING:
                self._log_message('WARNING', "Backup already running")
                return
            
            self.status = BackupStatus.RUNNING
            self.current_operation = "backup"
            self.progress = 0
            self.message = "Preparing backup..."
            self.start_time = time.time()
        
        try:
            self._log_message('INFO', f"Starting backup for volumes: {', '.join(selected_volumes)}")
            
            # Prepare paths to backup
            backup_paths = []
            for volume in selected_volumes:
                volume_path = f"/volumes/{volume}"
                if os.path.exists(volume_path):
                    backup_paths.append(volume_path)
                else:
                    self._log_message('WARNING', f"Volume path not found: {volume_path}")
            
            if not backup_paths:
                raise Exception("No valid volume paths found for backup")
            
            # Update progress
            with self.lock:
                self.progress = 25
                self.message = "Running backup..."
            
            # Run restic backup
            env = self._get_env_vars()
            cmd = ['restic', 'backup'] + backup_paths + [
                '--tag', 'docker-volumes',
                '--tag', f"backup-{datetime.now().strftime('%Y-%m-%d')}"
            ]
            
            self._log_message('INFO', f"Running command: {' '.join(cmd)}")
            
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Read output in real-time
            for line in process.stdout:
                line = line.strip()
                if line:
                    self._log_message('INFO', f"Restic: {line}")
                    
                    # Update progress based on output patterns
                    if "processed" in line.lower():
                        # Try to extract file count for better progress estimation
                        match = re.search(r'(\d+)\s+files', line)
                        if match:
                            files_processed = int(match.group(1))
                            # Rough progress estimation based on file count
                            progress_increment = min(5, max(1, files_processed // 100))
                            with self.lock:
                                self.progress = min(85, self.progress + progress_increment)
                                self.message = f"Processing files... ({files_processed} files)"
                    elif "backed up" in line.lower() or "snapshot" in line.lower():
                        with self.lock:
                            self.progress = min(95, self.progress + 10)
                            self.message = "Finalizing backup..."
                    elif "uploading" in line.lower():
                        with self.lock:
                            self.message = "Uploading to remote storage..."
            
            process.wait()
            
            if process.returncode == 0:
                with self.lock:
                    self.status = BackupStatus.SUCCESS
                    self.progress = 100
                    self.message = "Backup completed successfully"
                
                self._log_message('INFO', "Backup completed successfully")
                
                # Update last backup time in config
                self._update_last_backup_time()
                
            else:
                raise Exception(f"Backup failed with return code {process.returncode}")
                
        except Exception as e:
            with self.lock:
                self.status = BackupStatus.ERROR
                self.message = str(e)
            self._log_message('ERROR', f"Backup failed: {e}")
        
        finally:
            # Reset operation after a delay
            threading.Timer(5.0, self._reset_operation).start()
    
    def run_restore(self, snapshot_id, target_path):
        """Run restore for a specific snapshot"""
        with self.lock:
            if self.status == BackupStatus.RUNNING:
                self._log_message('WARNING', "Operation already running")
                return
            
            self.status = BackupStatus.RUNNING
            self.current_operation = "restore"
            self.progress = 0
            self.message = "Preparing restore..."
            self.start_time = time.time()
        
        try:
            self._log_message('INFO', f"Starting restore of snapshot {snapshot_id} to {target_path}")
            
            # Ensure target directory exists
            os.makedirs(target_path, exist_ok=True)
            
            # Update progress
            with self.lock:
                self.progress = 25
                self.message = "Running restore..."
            
            # Run restic restore
            env = self._get_env_vars()
            cmd = ['restic', 'restore', snapshot_id, '--target', target_path]
            
            self._log_message('INFO', f"Running command: {' '.join(cmd)}")
            
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Read output in real-time
            for line in process.stdout:
                line = line.strip()
                if line:
                    self._log_message('INFO', f"Restic: {line}")
                    
                    # Update progress based on output patterns
                    if "restored" in line.lower():
                        match = re.search(r'(\d+)\s+files', line)
                        if match:
                            files_restored = int(match.group(1))
                            progress_increment = min(5, max(1, files_restored // 50))
                            with self.lock:
                                self.progress = min(90, self.progress + progress_increment)
                                self.message = f"Restoring files... ({files_restored} files)"
                    elif "downloading" in line.lower():
                        with self.lock:
                            self.message = "Downloading from remote storage..."
            
            process.wait()
            
            if process.returncode == 0:
                with self.lock:
                    self.status = BackupStatus.SUCCESS
                    self.progress = 100
                    self.message = f"Restore completed successfully to {target_path}"
                
                self._log_message('INFO', f"Restore completed successfully to {target_path}")
            else:
                raise Exception(f"Restore failed with return code {process.returncode}")
                
        except Exception as e:
            with self.lock:
                self.status = BackupStatus.ERROR
                self.message = str(e)
            self._log_message('ERROR', f"Restore failed: {e}")
        
        finally:
            # Reset operation after a delay
            threading.Timer(5.0, self._reset_operation).start()
    
    def _update_last_backup_time(self):
        """Update the last backup time in configuration"""
        try:
            config_path = '/data/config.json'
            config = {}
            
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
            
            config['last_backup'] = datetime.now().isoformat()
            
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
                
        except Exception as e:
            self._log_message('ERROR', f"Failed to update last backup time: {e}")
    
    def _reset_operation(self):
        """Reset operation status"""
        with self.lock:
            if self.status != BackupStatus.RUNNING:
                self.current_operation = None
                self.progress = 0
                if hasattr(self, 'start_time'):
                    delattr(self, 'start_time')
                if hasattr(self, 'estimated_completion'):
                    delattr(self, 'estimated_completion')
                if self.status == BackupStatus.SUCCESS:
                    self.status = BackupStatus.IDLE
                    self.message = ""