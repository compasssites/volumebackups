import os
import json
import subprocess
import threading
import time
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from functools import wraps
import logging
import glob
from backup import BackupEngine, BackupStatus

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/data/app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize backup engine
backup_engine = BackupEngine()

# Configuration paths
CONFIG_PATH = '/data/config.json'
DATA_DIR = '/data'
VOLUMES_DIR = '/volumes'

def load_config():
    """Load configuration from JSON file"""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {}
    return {}

def save_config(config):
    """Save configuration to JSON file"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving config: {e}")
        return False

def discover_volumes():
    """Discover all mounted Docker volumes"""
    volumes = []
    if os.path.exists(VOLUMES_DIR):
        for item in os.listdir(VOLUMES_DIR):
            volume_path = os.path.join(VOLUMES_DIR, item)
            if os.path.isdir(volume_path):
                # Get volume size
                try:
                    result = subprocess.run(['du', '-sh', volume_path], 
                                          capture_output=True, text=True)
                    size = result.stdout.split()[0] if result.returncode == 0 else 'Unknown'
                except:
                    size = 'Unknown'
                
                volumes.append({
                    'name': item,
                    'path': volume_path,
                    'size': size
                })
    return volumes

def basic_auth(f):
    """Basic authentication decorator"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_user = os.environ.get('AUTH_USER')
        auth_pass = os.environ.get('AUTH_PASSWORD')
        
        if not auth_user or not auth_pass:
            return f(*args, **kwargs)
            
        auth = request.authorization
        if not auth or auth.username != auth_user or auth.password != auth_pass:
            return ('Authentication required', 401, {
                'WWW-Authenticate': 'Basic realm="Docker Volume Backup"'
            })
        return f(*args, **kwargs)
    return decorated

@app.route('/')
@basic_auth
def dashboard():
    """Main dashboard"""
    config = load_config()
    volumes = discover_volumes()
    status = backup_engine.get_status()
    
    # Get last backup info
    last_backup = config.get('last_backup')
    next_backup = None
    
    if config.get('schedule_enabled', True):
        # Calculate next backup (daily at 2 AM)
        now = datetime.now()
        next_backup = now.replace(hour=2, minute=0, second=0, microsecond=0)
        if now.hour >= 2:
            next_backup += timedelta(days=1)
    
    return render_template('dashboard.html', 
                         volumes=volumes, 
                         config=config,
                         status=status,
                         last_backup=last_backup,
                         next_backup=next_backup)

@app.route('/volumes')
@basic_auth
def volumes():
    """Volume management page"""
    volumes = discover_volumes()
    config = load_config()
    selected_volumes = config.get('selected_volumes', [])
    
    for volume in volumes:
        volume['selected'] = volume['name'] in selected_volumes
    
    return render_template('volumes.html', volumes=volumes)

@app.route('/api/volumes/select', methods=['POST'])
@basic_auth
def select_volumes():
    """Update selected volumes"""
    try:
        data = request.get_json()
        selected_volumes = data.get('volumes', [])
        
        config = load_config()
        config['selected_volumes'] = selected_volumes
        config['updated_at'] = datetime.now().isoformat()
        
        if save_config(config):
            return jsonify({'status': 'success', 'message': 'Volume selection updated'})
        else:
            return jsonify({'status': 'error', 'message': 'Failed to save configuration'})
    except Exception as e:
        logger.error(f"Error updating volume selection: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/backup')
@basic_auth
def backup_page():
    """Backup management page"""
    snapshots = backup_engine.list_snapshots()
    status = backup_engine.get_status()
    logs = backup_engine.get_recent_logs()
    
    return render_template('backup.html', 
                         snapshots=snapshots, 
                         status=status,
                         logs=logs)

@app.route('/api/backup/start', methods=['POST'])
@basic_auth
def start_backup():
    """Start a backup operation"""
    try:
        config = load_config()
        selected_volumes = config.get('selected_volumes', [])
        
        if not selected_volumes:
            return jsonify({'status': 'error', 'message': 'No volumes selected for backup'})
        
        # Start backup in background thread
        thread = threading.Thread(target=backup_engine.run_backup, args=(selected_volumes,))
        thread.daemon = True
        thread.start()
        
        return jsonify({'status': 'success', 'message': 'Backup started'})
    except Exception as e:
        logger.error(f"Error starting backup: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/restore/start', methods=['POST'])
@basic_auth
def start_restore():
    """Start a restore operation"""
    try:
        data = request.get_json()
        snapshot_id = data.get('snapshot_id')
        target_path = data.get('target_path', '/data/restore')
        
        if not snapshot_id:
            return jsonify({'status': 'error', 'message': 'Snapshot ID required'})
        
        # Start restore in background thread
        thread = threading.Thread(target=backup_engine.run_restore, 
                                args=(snapshot_id, target_path))
        thread.daemon = True
        thread.start()
        
        return jsonify({'status': 'success', 'message': 'Restore started'})
    except Exception as e:
        logger.error(f"Error starting restore: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/status')
@basic_auth
def get_status():
    """Get current backup/restore status"""
    return jsonify(backup_engine.get_status())

@app.route('/api/logs')
@basic_auth
def get_logs():
    """Get recent logs"""
    return jsonify(backup_engine.get_recent_logs())

@app.route('/config')
@basic_auth
def config_page():
    """Configuration management page"""
    config = load_config()
    env_vars = {
        'RESTIC_PASSWORD': bool(os.environ.get('RESTIC_PASSWORD')),
        'RCLONE_REMOTE': os.environ.get('RCLONE_REMOTE', ''),
        'RCLONE_FOLDER': os.environ.get('RCLONE_FOLDER', ''),
        'TZ': os.environ.get('TZ', 'UTC')
    }
    
    return render_template('config.html', config=config, env_vars=env_vars)

@app.route('/api/config/update', methods=['POST'])
@basic_auth
def update_config():
    """Update configuration"""
    try:
        data = request.get_json()
        config = load_config()
        
        # Update configuration
        for key, value in data.items():
            config[key] = value
        
        config['updated_at'] = datetime.now().isoformat()
        
        if save_config(config):
            return jsonify({'status': 'success', 'message': 'Configuration updated'})
        else:
            return jsonify({'status': 'error', 'message': 'Failed to save configuration'})
    except Exception as e:
        logger.error(f"Error updating configuration: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/logs')
@basic_auth
def logs_page():
    """Logs viewing page"""
    logs = backup_engine.get_recent_logs(limit=100)
    return render_template('logs.html', logs=logs)

if __name__ == '__main__':
    # Ensure data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Start the Flask app
    app.run(host='0.0.0.0', port=5000, debug=False)