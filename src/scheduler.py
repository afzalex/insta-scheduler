import pandas as pd
import yaml
from datetime import datetime, timedelta
import time
import subprocess
from pathlib import Path
import logging
from .window_tracker import WindowTracker
import signal
import atexit

logger = logging.getLogger(__name__)

class SchedulerConfigError(Exception):
    """Raised when there are issues with scheduler configuration"""
    pass

class MediaStatus:
    PENDING = ""  # Default/empty state
    ERROR = "ERROR"
    PROCESSED = "PROCESSED"

    @classmethod
    def is_pending(cls, status):
        """
        Check if a status value represents a pending state
        
        Args:
            status: Status value to check
            
        Returns:
            bool: True if status represents pending state
        """
        return status != cls.ERROR and status != cls.PROCESSED

class MediaScheduler:
    def __init__(self, config_path=None):
        """Initialize scheduler with config file path"""
        self.config_path = config_path
        self.config = None
        self.media_df = None
        self.schedule_times = []
        self.schedule_config = {}
        self.current_window = None
        self.tasks_in_window = 0
        self.extra_caption = None  # Store extra caption
        self.window_tracker = WindowTracker()
        self.has_lock = False  # Track if this instance created the lock
        self.headless = True  # Default to headless mode
        
        # Register cleanup handlers
        atexit.register(self._cleanup)
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
    def _cleanup(self):
        """Cleanup resources"""
        if self.has_lock:  # Only cleanup if we created the lock
            logger.info("Cleaning up scheduler resources")
            self.window_tracker.release_lock()
            self.has_lock = False
        
    def _signal_handler(self, signum, frame):
        """Handle termination signals"""
        sig_name = signal.Signals(signum).name
        logger.info(f"Received signal {sig_name}, shutting down gracefully")
        # Run cleanup and exit
        self._cleanup()
        exit(0)

    def validate_and_load_config(self):
        """Validate and load all configuration files"""
        try:
            with open(self.config_path) as f:
                self.config = yaml.safe_load(f)
                
            required_keys = ['schedule', 'media_list']
            missing = [k for k in required_keys if k not in self.config]
            if missing:
                raise SchedulerConfigError(f"Missing required keys: {missing}")
                
            # Get extra caption if provided
            self.extra_caption = self.config.get('extra_caption', None)
                
            # Validate required fields
            if 'schedule' not in self.config:
                raise SchedulerConfigError("Missing 'schedule' in config")
            if 'media_list' not in self.config:
                raise SchedulerConfigError("Missing 'media_list' in config")
                
            # Validate schedule entries and set defaults
            for entry in self.config['schedule']:
                if 'time' not in entry:
                    raise SchedulerConfigError("Schedule entry missing required 'time' field")
                # Set defaults for optional fields
                entry.setdefault('window_hours', 0)
                entry.setdefault('max_tasks', 1)
                    
        except yaml.YAMLError as e:
            raise SchedulerConfigError(f"Invalid YAML in scheduler config: {e}")
            
        # Check and load media list
        media_list_path = Path(self.config['media_list'])
        if not media_list_path.exists():
            raise SchedulerConfigError(f"Media list not found: {media_list_path}")
            
        try:
            self.media_df = pd.read_csv(media_list_path)
            required_columns = ['file_path', 'caption']
            missing = [c for c in required_columns if c not in self.media_df.columns]
            if missing:
                raise SchedulerConfigError(f"Media list missing columns: {missing}")
                
            # Initialize status column if it doesn't exist
            if '_STATUS_' not in self.media_df.columns:
                logger.info("Adding _STATUS_ column to media list")
                self.media_df['_STATUS_'] = MediaStatus.PENDING
                # Save the updated DataFrame
                self.media_df.to_csv(media_list_path, index=False)
                logger.info("Media list updated with _STATUS_ column")
                
        except pd.errors.EmptyDataError:
            raise SchedulerConfigError("Media list file is empty")
        except pd.errors.ParserError as e:
            raise SchedulerConfigError(f"Invalid CSV format in media list: {e}")
            
        # Sort schedule times for consistent ordering
        self.schedule_times = sorted([s['time'] for s in self.config['schedule']])
        self.schedule_config = {s['time']: s for s in self.config['schedule']}
        
        # Track tasks completed in current window
        self.current_window = None
        self.tasks_in_window = 0

    def update_media_list(self, new_path):
        """Update media list path and reload configuration"""
        self.config['media_list'] = str(new_path)
        self.validate_and_load_config()

    def get_next_schedule_time(self, from_time=None):
        """Calculate the next schedule time"""
        if from_time is None:
            from_time = datetime.now()
            
        current_time = from_time.strftime("%H:%M")
        
        # First check if we're in any current window
        for time_slot in self.schedule_times:
            slot_time = datetime.combine(from_time.date(), 
                                       datetime.strptime(time_slot, "%H:%M").time())
            window_hours = self.schedule_config[time_slot]['window_hours']
            window_end = slot_time + timedelta(hours=window_hours)
            
            # If current time is within this window, return this slot
            if slot_time <= from_time <= window_end:
                return slot_time
        
        # If not in any current window, find next time slot today
        next_today = next(
            (t for t in self.schedule_times if t > current_time),
            None
        )
        
        if next_today:
            next_time = datetime.combine(from_time.date(), 
                                       datetime.strptime(next_today, "%H:%M").time())
        else:
            # If no remaining slots today, get first slot tomorrow
            next_time = datetime.combine(from_time.date() + timedelta(days=1), 
                                       datetime.strptime(self.schedule_times[0], "%H:%M").time())
        
        return next_time

    def is_within_window(self, schedule_time):
        """Check if current time is within the window of a scheduled time"""
        now = datetime.now()
        window_config = self.schedule_config[schedule_time.strftime("%H:%M")]
        window_end = schedule_time + timedelta(hours=window_config['window_hours'])
        
        # Reset task counter if we've moved to a new window
        if self.current_window != schedule_time:
            self.current_window = schedule_time
            window_key = schedule_time.strftime("%Y-%m-%d %H:%M")
            self.tasks_in_window = self.window_tracker.get_tasks_in_window(window_key)
            
        # Check if we're within window and haven't exceeded max tasks
        if schedule_time <= now <= window_end:
            max_tasks = window_config['max_tasks']
            if self.tasks_in_window < max_tasks:
                return True
            else:
                logger.info(f"Maximum tasks ({max_tasks}) already completed for this window")
        
        return False

    def get_next_unprocessed_media(self):
        """Get the next unprocessed media items if within posting window"""
        # Reload media list to get latest status
        media_list_path = Path(self.config['media_list'])
        try:
            self.media_df = pd.read_csv(media_list_path)
            
            # Add _STATUS_ column if it doesn't exist
            if '_STATUS_' not in self.media_df.columns:
                self.media_df['_STATUS_'] = MediaStatus.PENDING
                self.media_df.to_csv(media_list_path, index=False)
                
        except Exception as e:
            logger.error(f"Failed to reload media list: {e}")
            return None

        # Consider anything that's not explicitly PROCESSED or ERROR as pending
        unprocessed = self.media_df[self.media_df['_STATUS_'].apply(MediaStatus.is_pending)]
        if unprocessed.empty:
            logger.info("No unprocessed media items remaining")
            return None
            
        # Get next schedule time
        schedule_time = self.get_next_schedule_time()
        
        # Check if we're within the posting window
        if self.is_within_window(schedule_time):
            # Get first unprocessed item
            next_item = unprocessed.iloc[0]
            self.tasks_in_window += 1
            return next_item
            
        return None

    def mark_status(self, media_path, status):
        """
        Mark a media item with the given status
        
        Args:
            media_path: Path to the media file
            status: Status to set (use MediaStatus constants)
        """
        try:
            idx = self.media_df[self.media_df['file_path'] == media_path].index
            self.media_df.loc[idx, '_STATUS_'] = status
            # Immediately write to file to persist the status
            self.media_df.to_csv(self.config['media_list'], index=False)
            logger.info(f"Marked {media_path} as {status}")
        except Exception as e:
            logger.error(f"Failed to mark item status: {e}")

    def insta_upload(self, media_item):
        """Run the upload script with the media item"""
        try:
            command = [
                'python', 'run.py', 'insta-upload',
                '-f', media_item['file_path'],
                '-c', media_item['caption']
            ]
            
            # Add extra caption if provided
            if self.extra_caption:
                command.extend(['--extra-caption', self.extra_caption])
                
            # Add no-headless flag if headless is False
            if not self.headless:
                command.append('--no-headless')
                
            result = subprocess.run(command, check=True)
            
            if result.returncode == 0:
                self.mark_status(media_item['file_path'], MediaStatus.PROCESSED)
                logger.info(f"Successfully processed {media_item['file_path']}")
                self.tasks_in_window += 1
                # Record task in window tracker
                if self.current_window:
                    window_key = self.current_window.strftime("%Y-%m-%d %H:%M")
                    self.window_tracker.record_task(window_key, self.tasks_in_window)
                logger.info(f"Tasks completed in current window: {self.tasks_in_window}")
                return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to process {media_item['file_path']}: {e}")
            self.mark_status(media_item['file_path'], MediaStatus.ERROR)
            # Decrement task counter if upload fails
            self.tasks_in_window -= 1
        return False

    def run(self):
        """Main scheduler loop"""
        # Create lock file
        if not self.window_tracker.create_lock():
            logger.error("Another instance of scheduler is already running")
            logger.info("If you are sure no other instance is running, you can manually delete the lock file:")
            logger.info(f"    rm {self.window_tracker.lock_file}")
            return False
            
        self.has_lock = True  # Mark that we created the lock
        
        try:
            while True:
                next_schedule = self.get_next_schedule_time()
                now = datetime.now()
                
                # If next schedule is in future, print waiting message
                if next_schedule > now:
                    wait_time = next_schedule - now
                    hours, remainder = divmod(wait_time.seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    time_str = []
                    if hours > 0:
                        time_str.append(f"{hours} hour{'s' if hours != 1 else ''}")
                    if minutes > 0:
                        time_str.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
                    if seconds > 0 and not hours and minutes < 5:  # Only show seconds if less than 5 minutes away
                        time_str.append(f"{seconds} second{'s' if seconds != 1 else ''}")
                    
                    wait_str = " and ".join(time_str) if len(time_str) <= 2 else ", ".join(time_str[:-1]) + f" and {time_str[-1]}"
                    logger.info(f"Waiting for next scheduled task at {next_schedule.strftime('%H:%M')} ({wait_str} from now)")
                
                media_item = self.get_next_unprocessed_media()
                
                if media_item is not None:
                    logger.info(f"Processing media: {media_item['file_path']}")
                    self.insta_upload(media_item)
                
                # Sleep for a minute before checking again
                time.sleep(60)
        except Exception as e:
            logger.exception("Error in scheduler loop")
            return False
        finally:
            # Release lock file when done
            self._cleanup()

def main(config_path=None, media_list=None, headless=True):
    """
    Run the scheduler with the specified configuration
    
    Args:
        config_path: Path to scheduler config YAML file
        media_list: Path to media list CSV file (overrides config)
        headless: Whether to run in headless mode (default: True)
        
    Returns:
        int: Exit code (0 for success, 1 for error)
    """
    try:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
        scheduler = MediaScheduler(config_path=config_path or "config/scheduler_config.yml")
        scheduler.headless = headless  # Set headless mode
        
        # Check if scheduler is already running
        if scheduler.window_tracker.is_scheduler_running():
            logger.error("Another instance of scheduler is already running")
            logger.info("If you are sure no other instance is running, you can manually delete the lock file:")
            logger.info(f"    rm {scheduler.window_tracker.lock_file}")
            return 1
            
        scheduler.validate_and_load_config()  # Load config after initialization
        
        if media_list:
            scheduler.update_media_list(media_list)
            
        if not scheduler.run():
            return 1
            
        return 0
        
    except SchedulerConfigError as e:
        logger.error(f"Configuration error: {e}")
        return 1
    except Exception as e:
        logger.exception("Unexpected error occurred")
        return 1

if __name__ == "__main__":
    exit(main()) 