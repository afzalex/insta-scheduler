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
from croniter import croniter, CroniterNotAlphaError, CroniterBadCronError

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
        """Check if a status value represents a pending state"""
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
        self.extra_caption = None
        self.window_tracker = WindowTracker()
        self.has_lock = False
        self.headless = True
        self.force = False  # Add force flag
        self.cron_iters = []  # Store cron iterators
        
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
                
            self.extra_caption = self.config.get('extra_caption', None)
                
            if 'schedule' not in self.config:
                raise SchedulerConfigError("Missing 'schedule' in config")
            if 'media_list' not in self.config:
                raise SchedulerConfigError("Missing 'media_list' in config")
                
            # Validate schedule entries and set defaults
            for entry in self.config['schedule']:
                if 'cron' not in entry:
                    raise SchedulerConfigError("Schedule entry missing required 'cron' field")
                try:
                    # Validate cron expression
                    croniter(entry['cron'])  # Just validate, don't store
                except (CroniterNotAlphaError, CroniterBadCronError) as e:
                    raise SchedulerConfigError(f"Invalid cron expression '{entry['cron']}': {e}")
                
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
            required_columns = ['file_path']  # Only file_path is required
            missing = [c for c in required_columns if c not in self.media_df.columns]
            if missing:
                raise SchedulerConfigError(f"Media list missing columns: {missing}")
                
            # Initialize status column if it doesn't exist
            if '_STATUS_' not in self.media_df.columns:
                logger.info("Adding _STATUS_ column to media list")
                self.media_df['_STATUS_'] = MediaStatus.PENDING
                self.media_df.to_csv(media_list_path, index=False)
                logger.info("Media list updated with _STATUS_ column")
                
        except pd.errors.EmptyDataError:
            raise SchedulerConfigError("Media list file is empty")
        except pd.errors.ParserError as e:
            raise SchedulerConfigError(f"Invalid CSV format in media list: {e}")
            
        # Initialize cron iterators for each schedule
        self.cron_iters = [croniter(entry['cron'], datetime.now()) for entry in self.config['schedule']]
        self.schedule_config = {i: entry for i, entry in enumerate(self.config['schedule'])}

    def update_media_list(self, new_path):
        """Update media list path and reload configuration"""
        self.config['media_list'] = str(new_path)
        self.validate_and_load_config()

    def get_next_schedule_time(self, from_time=None):
        """Calculate the next schedule time"""
        if from_time is None:
            from_time = datetime.now()

        # First check if we're in any current window
        current_times = []
        for i, cron in enumerate(self.cron_iters):
            # Reset iterator to current time
            cron = croniter(self.config['schedule'][i]['cron'], from_time)
            window_hours = self.schedule_config[i]['window_hours']
            
            # Get the most recent schedule time
            last_time = cron.get_prev(datetime)
            
            # Check previous schedule times within max window duration
            # This ensures we don't miss a window that started earlier
            max_window_hours = max(entry['window_hours'] for entry in self.config['schedule'])
            check_range = timedelta(hours=max_window_hours)
            earliest_check = from_time - check_range
            
            while last_time >= earliest_check:
                window_end = last_time + timedelta(hours=window_hours)
                # If current time is within this window
                if last_time <= from_time <= window_end:
                    current_times.append((last_time, i))
                try:
                    last_time = cron.get_prev(datetime)
                except:
                    break  # Stop if we can't get more previous times

        # If we're in any window, return the earliest one
        if current_times:
            current_time, config_idx = min(current_times, key=lambda x: x[0])
            self.current_schedule_idx = config_idx
            return current_time

        # If not in any window, find next schedule time
        next_times = []
        for i, cron in enumerate(self.cron_iters):
            # Reset iterator to current time
            cron = croniter(self.config['schedule'][i]['cron'], from_time)
            next_time = cron.get_next(datetime)
            next_times.append((next_time, i))

        # Return the earliest next time
        if next_times:
            next_time, config_idx = min(next_times, key=lambda x: x[0])
            self.current_schedule_idx = config_idx
            return next_time
            
        return None

    def is_within_window(self, schedule_time):
        """Check if current time is within the window of a scheduled time"""
        now = datetime.now()
        window_config = self.schedule_config[self.current_schedule_idx]
        window_hours = window_config['window_hours']
        window_end = schedule_time + timedelta(hours=window_hours)
        
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
        """Get the next unprocessed media item"""
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
            
        # Get first unprocessed item
        return unprocessed.iloc[0]

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
                '-f', media_item['file_path']
            ]
            
            # Add caption if it exists in media list and is not empty
            if 'caption' in media_item and pd.notna(media_item['caption']):
                command.extend(['-c', media_item['caption']])
            
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
        # Create lock file (unless force is True)
        if not self.force and not self.window_tracker.create_lock():
            logger.error("Another instance of scheduler is already running")
            logger.info("If you are sure no other instance is running, you can:")
            logger.info("1. Delete the lock file: rm data/scheduler.lock")
            logger.info("2. Use --force to bypass this check")
            return False
            
        # If force is True, try to create lock but don't fail if it exists
        if self.force:
            self.window_tracker.create_lock()
            
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
                    time.sleep(60)
                    continue

                # Check if we're in a posting window
                if not self.is_within_window(next_schedule):
                    time.sleep(60)
                    continue

                # Get next unprocessed media
                media_item = self.get_next_unprocessed_media()
                if media_item is not None:
                    logger.info(f"Processing media: {media_item['file_path']}")
                    self.insta_upload(media_item)
                else:
                    # No media to process, wait longer
                    logger.info("No unprocessed media available, waiting 5 minutes before checking again")
                    time.sleep(300)  # Wait 5 minutes before checking again
                
                # Short sleep before next iteration
                time.sleep(60)
        except Exception as e:
            logger.exception("Error in scheduler loop")
            return False
        finally:
            # Release lock file when done
            self._cleanup()

def main(config_path=None, media_list=None, headless=True, force=False):
    """
    Run the scheduler with the specified configuration
    
    Args:
        config_path: Path to scheduler config YAML file
        media_list: Path to media list CSV file (overrides config)
        headless: Whether to run in headless mode (default: True)
        force: Whether to bypass instance check (default: False)
        
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
        scheduler.force = force  # Set force flag
        
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