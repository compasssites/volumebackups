#!/usr/bin/env python3
"""
Cron script for automated backups
"""

import os
import json
import sys
from datetime import datetime

# Add the app directory to the Python path
sys.path.insert(0, '/app')

from backup import BackupEngine

def main():
    """Run automated backup if enabled"""
    config_path = '/data/config.json'
    
    # Load configuration
    config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            return
    
    # Check if scheduled backups are enabled
    if not config.get('schedule_enabled', True):
        print("Scheduled backups are disabled")
        return
    
    # Get selected volumes
    selected_volumes = config.get('selected_volumes', [])
    if not selected_volumes:
        print("No volumes selected for backup")
        return
    
    # Check if restic password is set
    if not os.environ.get('RESTIC_PASSWORD'):
        print("RESTIC_PASSWORD not set")
        return
    
    print(f"Starting scheduled backup at {datetime.now()}")
    print(f"Selected volumes: {', '.join(selected_volumes)}")
    
    # Run backup
    backup_engine = BackupEngine()
    backup_engine.run_backup(selected_volumes)
    
    print(f"Backup completed at {datetime.now()}")

if __name__ == '__main__':
    main()