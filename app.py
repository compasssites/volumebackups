import os
import json
import subprocess
import threading
import time
import tempfile
import zipfile
import io
import hashlib
import secrets
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_file, Response, session
from functools import wraps
import logging
import glob
from crontab import CronTab
from backup import BackupEngine, BackupStatus

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

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
RCLONE_CONFIG_PATH = '/data/rclone.conf'
USER_CONFIG_PATH = '/data/users.json'

# Default credentials
DEFAULT_USERNAME = os.environ.get('WEB_USERNAME', 'admin')
DEFAULT_PASSWORD = os.environ.get('WEB_PASSWORD', 'admin123')
DEFAULT_SECRET_QUESTION = 'What is your favorite color?'
DEFAULT_SECRET_ANSWER = 'blue'

def init_user_config():
    """Initialize user configuration with default credentials"""
    if not os.path.exists(USER_CONFIG_PATH):
        default_user = {
            'username': DEFAULT_USERNAME,
            'password_hash': hashlib.sha256(DEFAULT_PASSWORD.encode()).hexdigest(),
            'secret_question': DEFAULT_SECRET_QUESTION,
            'secret_answer_hash': hashlib.sha256(DEFAULT_SECRET_ANSWER.lower().encode()).hexdigest()
        }
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(USER_CONFIG_PATH, 'w') as f:
                json.dump(default_user, f, indent=2)
            logger.info("Initialized default user configuration")
        except Exception as e:
            logger.error(f"Error initializing user config: {e}")

def load_user_config():
    """Load user configuration"""
    try:
        with open(USER_CONFIG_PATH, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading user config: {e}")
        return None

def save_user_config(user_config):
    """Save user configuration"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(USER_CONFIG_PATH, 'w') as f:
            json.dump(user_config, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving user config: {e}")
        return False

def verify_password(password, password_hash):
    """Verify password against hash"""
    return hashlib.sha256(password.encode()).hexdigest() == password_hash

def verify_secret_answer(answer, answer_hash):
    """Verify secret answer against hash"""
    return hashlib.sha256(answer.lower().encode()).hexdigest() == answer_hash

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session or not session['logged_in']:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

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

def get_cron_schedule():
    """Get current backup schedule from crontab"""
    try:
        cron = CronTab(user=True)
        for job in cron:
            if 'cron_backup.py' in job.command:
                return {
                    'minute': str(job.minute),
                    'hour': str(job.hour),
                    'day': str(job.day),
                    'month': str(job.month),
                    'dow': str(job.dow),
                    'enabled': job.is_enabled()
                }
    except Exception as e:
        logger.error(f"Error reading cron schedule: {e}")
    
    # Default schedule (2 AM daily)
    return {
        'minute': '0',
        'hour': '2',
        'day': '*',
        'month': '*',
        'dow': '*',
        'enabled': True
    }

def update_cron_schedule(schedule):
    """Update backup schedule in crontab"""
    try:
        cron = CronTab(user=True)
        
        # Remove existing backup jobs
        cron.remove_all(comment='backup-job')
        
        if schedule.get('enabled', True):
            # Add new job
            job = cron.new(command=f'cd /app && /usr/local/bin/python /app/cron_backup.py >> /data/cron.log 2>&1',
                          comment='backup-job')
            job.setall(f"{schedule['minute']} {schedule['hour']} {schedule['day']} {schedule['month']} {schedule['dow']}")
            job.enable()
        
        cron.write()
        return True
    except Exception as e:
        logger.error(f"Error updating cron schedule: {e}")
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

def load_rclone_config():
    """Load rclone configuration file"""
    if os.path.exists(RCLONE_CONFIG_PATH):
        try:
            with open(RCLONE_CONFIG_PATH, 'r') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error loading rclone config: {e}")
    return ""

def save_rclone_config(content):
    """Save rclone configuration file"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(RCLONE_CONFIG_PATH, 'w') as f:
            f.write(content)
        return True
    except Exception as e:
        logger.error(f"Error saving rclone config: {e}")
        return False

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user_config = load_user_config()
        if not user_config:
            flash('System error: Unable to load user configuration', 'error')
            return render_template('login.html')
        
        if (username == user_config['username'] and 
            verify_password(password, user_config['password_hash'])):
            session['logged_in'] = True
            session['username'] = username
            flash('Login successful', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Forgot password page"""
    if request.method == 'POST':
        username = request.form.get('username')
        secret_answer = request.form.get('secret_answer')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        user_config = load_user_config()
        if not user_config:
            flash('System error: Unable to load user configuration', 'error')
            return render_template('forgot_password.html')
        
        if username != user_config['username']:
            flash('Invalid username', 'error')
            return render_template('forgot_password.html')
        
        if not verify_secret_answer(secret_answer, user_config['secret_answer_hash']):
            flash('Incorrect answer to security question', 'error')
            return render_template('forgot_password.html')
        
        if new_password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('forgot_password.html')
        
        if len(new_password) < 6:
            flash('Password must be at least 6 characters long', 'error')
            return render_template('forgot_password.html')
        
        # Update password
        user_config['password_hash'] = hashlib.sha256(new_password.encode()).hexdigest()
        if save_user_config(user_config):
            flash('Password reset successfully. Please login with your new password.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Error saving new password. Please try again.', 'error')
    
    user_config = load_user_config()
    secret_question = user_config.get('secret_question', 'Security question not set') if user_config else 'Security question not set'
    
    return render_template('forgot_password.html', secret_question=secret_question)

@app.route('/logout')
def logout():
    """Logout and clear session"""
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    """Main dashboard"""
    config = load_config()
    volumes = discover_volumes()
    status = backup_engine.get_status()
    schedule = get_cron_schedule()
    
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
                         schedule=schedule,
                         last_backup=last_backup,
                         next_backup=next_backup)

@app.route('/volumes')
@login_required
def volumes():
    """Volume management page"""
    volumes = discover_volumes()
    config = load_config()
    selected_volumes = config.get('selected_volumes', [])
    
    for volume in volumes:
        volume['selected'] = volume['name'] in selected_volumes
    
    return render_template('volumes.html', volumes=volumes)

@app.route('/api/volumes/select', methods=['POST'])
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
def get_status():
    """Get current backup/restore status"""
    return jsonify(backup_engine.get_status())

@app.route('/api/logs')
@login_required
def get_logs():
    """Get recent logs"""
    return jsonify(backup_engine.get_recent_logs())

@app.route('/config')
@login_required
def config_page():
    """Configuration management page"""
    config = load_config()
    schedule = get_cron_schedule()
    rclone_config = load_rclone_config()
    env_vars = {
        'RESTIC_PASSWORD': bool(os.environ.get('RESTIC_PASSWORD')),
        'RCLONE_REMOTE': os.environ.get('RCLONE_REMOTE', ''),
        'RCLONE_FOLDER': os.environ.get('RCLONE_FOLDER', ''),
        'TZ': os.environ.get('TZ', 'UTC')
    }
    
    return render_template('config.html', config=config, env_vars=env_vars, 
                         schedule=schedule, rclone_config=rclone_config)

@app.route('/api/config/update', methods=['POST'])
@login_required
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

@app.route('/api/schedule/update', methods=['POST'])
@login_required
def update_schedule():
    """Update backup schedule"""
    try:
        data = request.get_json()
        
        schedule = {
            'minute': data.get('minute', '0'),
            'hour': data.get('hour', '2'),
            'day': data.get('day', '*'),
            'month': data.get('month', '*'),
            'dow': data.get('dow', '*'),
            'enabled': data.get('enabled', True)
        }
        
        if update_cron_schedule(schedule):
            return jsonify({'status': 'success', 'message': 'Schedule updated successfully'})
        else:
            return jsonify({'status': 'error', 'message': 'Failed to update schedule'})
    except Exception as e:
        logger.error(f"Error updating schedule: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/rclone/config', methods=['GET', 'POST'])
@login_required
def rclone_config():
    """Get or update rclone configuration"""
    if request.method == 'GET':
        config_content = load_rclone_config()
        return jsonify({'config': config_content})
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            config_content = data.get('config', '')
            
            if save_rclone_config(config_content):
                return jsonify({'status': 'success', 'message': 'Rclone configuration saved'})
            else:
                return jsonify({'status': 'error', 'message': 'Failed to save configuration'})
        except Exception as e:
            logger.error(f"Error updating rclone config: {e}")
            return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/rclone/test', methods=['POST'])
@login_required
def test_rclone():
    """Test rclone connection"""
    try:
        env = os.environ.copy()
        env['RCLONE_CONFIG'] = RCLONE_CONFIG_PATH
        
        remote = os.environ.get('RCLONE_REMOTE', 'onedrive')
        
        result = subprocess.run([
            'rclone', 'lsd', f'{remote}:'
        ], env=env, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            return jsonify({
                'status': 'success', 
                'message': 'Rclone connection successful',
                'output': result.stdout
            })
        else:
            return jsonify({
                'status': 'error', 
                'message': 'Rclone connection failed',
                'error': result.stderr
            })
    except Exception as e:
        logger.error(f"Error testing rclone: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/download/logs')
@login_required
def download_logs():
    """Download application logs as a zip file"""
    try:
        # Create a temporary zip file
        memory_file = io.BytesIO()
        
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add application log
            if os.path.exists('/data/app.log'):
                zf.write('/data/app.log', 'app.log')
            
            # Add cron log
            if os.path.exists('/data/cron.log'):
                zf.write('/data/cron.log', 'cron.log')
            
            # Add configuration
            if os.path.exists(CONFIG_PATH):
                zf.write(CONFIG_PATH, 'config.json')
            
            # Add recent logs from backup engine
            logs = backup_engine.get_recent_logs(limit=1000)
            if logs:
                logs_content = '\n'.join([
                    f"[{log['timestamp']}] {log['level']}: {log['message']}"
                    for log in logs
                ])
                zf.writestr('backup_engine.log', logs_content)
        
        memory_file.seek(0)
        
        return send_file(
            io.BytesIO(memory_file.read()),
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'backup-logs-{datetime.now().strftime("%Y%m%d-%H%M%S")}.zip'
        )
    except Exception as e:
        logger.error(f"Error creating log download: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/download/backup/<snapshot_id>')
@login_required
def download_backup(snapshot_id):
    """Download a backup snapshot as a tar.gz file"""
    try:
        # Create temporary directory for extraction
        with tempfile.TemporaryDirectory() as temp_dir:
            extract_path = os.path.join(temp_dir, 'backup')
            os.makedirs(extract_path)
            
            # Restore backup to temporary location
            env = backup_engine._get_env_vars()
            env['RCLONE_CONFIG'] = RCLONE_CONFIG_PATH
            
            result = subprocess.run([
                'restic', 'restore', snapshot_id, '--target', extract_path
            ], env=env, capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                return jsonify({'status': 'error', 'message': f'Failed to extract backup: {result.stderr}'}), 500
            
            # Create tar.gz archive
            archive_path = os.path.join(temp_dir, f'backup-{snapshot_id}.tar.gz')
            subprocess.run([
                'tar', '-czf', archive_path, '-C', extract_path, '.'
            ], check=True)
            
            return send_file(
                archive_path,
                mimetype='application/gzip',
                as_attachment=True,
                download_name=f'backup-{snapshot_id}.tar.gz'
            )
    except Exception as e:
        logger.error(f"Error creating backup download: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/logs')
@login_required
def logs_page():
    """Logs viewing page"""
    logs = backup_engine.get_recent_logs(limit=100)
    return render_template('logs.html', logs=logs)

@app.route('/api/status/detailed')
@login_required
def get_detailed_status():
    """Get detailed status including system information"""
    status = backup_engine.get_status()
    
    # Add system information
    try:
        # Get disk usage
        data_usage = subprocess.run(['du', '-sh', '/data'], capture_output=True, text=True)
        volumes_usage = subprocess.run(['du', '-sh', '/volumes'], capture_output=True, text=True)
        
        status['system'] = {
            'data_usage': data_usage.stdout.split()[0] if data_usage.returncode == 0 else 'Unknown',
            'volumes_usage': volumes_usage.stdout.split()[0] if volumes_usage.returncode == 0 else 'Unknown',
            'uptime': subprocess.run(['uptime', '-p'], capture_output=True, text=True).stdout.strip()
        }
    except:
        status['system'] = {}
    
    return jsonify(status)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile management"""
    user_config = load_user_config()
    if not user_config:
        flash('Error loading user configuration', 'error')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'change_password':
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            if not verify_password(current_password, user_config['password_hash']):
                flash('Current password is incorrect', 'error')
            elif new_password != confirm_password:
                flash('New passwords do not match', 'error')
            elif len(new_password) < 6:
                flash('Password must be at least 6 characters long', 'error')
            else:
                user_config['password_hash'] = hashlib.sha256(new_password.encode()).hexdigest()
                if save_user_config(user_config):
                    flash('Password changed successfully', 'success')
                else:
                    flash('Error saving new password', 'error')
        
        elif action == 'update_security':
            secret_question = request.form.get('secret_question')
            secret_answer = request.form.get('secret_answer')
            
            if not secret_question or not secret_answer:
                flash('Both security question and answer are required', 'error')
            else:
                user_config['secret_question'] = secret_question
                user_config['secret_answer_hash'] = hashlib.sha256(secret_answer.lower().encode()).hexdigest()
                if save_user_config(user_config):
                    flash('Security question updated successfully', 'success')
                else:
                    flash('Error updating security question', 'error')
    
    return render_template('profile.html', 
                         username=user_config['username'],
                         secret_question=user_config.get('secret_question', ''))

if __name__ == '__main__':
    # Ensure data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Initialize user configuration
    init_user_config()
    
    # Set rclone config path
    os.environ['RCLONE_CONFIG'] = RCLONE_CONFIG_PATH
    
    # Start the Flask app
    app.run(host='0.0.0.0', port=5000, debug=False)