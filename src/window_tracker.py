import json
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class WindowTracker:
    def __init__(self, data_dir="data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.window_file = self.data_dir / "window_tasks.json"
        self.lock_file = self.data_dir / "scheduler.lock"
        
    def is_scheduler_running(self):
        """Check if scheduler is already running"""
        return self.lock_file.exists()
        
    def create_lock(self):
        """Create scheduler lock file"""
        try:
            self.lock_file.touch(exist_ok=False)
            return True
        except FileExistsError:
            return False
            
    def release_lock(self):
        """Release scheduler lock file"""
        try:
            self.lock_file.unlink(missing_ok=True)
        except Exception as e:
            logger.error(f"Failed to release lock: {e}")
            
    def get_window_tasks(self):
        """Get tasks executed in windows"""
        if not self.window_file.exists():
            return {}
        try:
            with open(self.window_file) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read window tasks: {e}")
            return {}
            
    def save_window_tasks(self, tasks):
        """Save window tasks to file"""
        try:
            with open(self.window_file, 'w') as f:
                json.dump(tasks, f)
        except Exception as e:
            logger.error(f"Failed to save window tasks: {e}")
            
    def record_task(self, window_time, task_count):
        """Record tasks executed in a window"""
        tasks = self.get_window_tasks()
        tasks[window_time] = task_count
        self.save_window_tasks(tasks)
        
    def get_tasks_in_window(self, window_time):
        """Get number of tasks executed in a window"""
        tasks = self.get_window_tasks()
        return tasks.get(window_time, 0) 