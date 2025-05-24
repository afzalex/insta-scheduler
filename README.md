# Instagram Post Scheduler

An automated tool for scheduling and uploading posts to Instagram. It manages timed posts with AI-generated captions and customizable scheduling windows, supporting various types of media content.

## Features

- Schedule Instagram posts at specific times
- Support for multiple daily upload windows
- AI-powered caption generation using BLIP
- Headless mode for background operation
- Lock-based scheduler to prevent multiple instances
- Persistent tracking of upload status and window tasks
- Customizable hashtags and captions for posts

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd insta-scheduler
```

2. Create and activate conda environment:
```bash
# Create environment from yml file
conda env create -f environment.yml

# Activate the environment
conda activate insta-scheduler
```

3. Verify installation:
```bash
# Should show all installed packages
conda list
```

To update environment after changes to environment.yml:
```bash
conda env update -f environment.yml --prune
```

## Configuration

### Scheduler Configuration

Create or modify `config/scheduler_config.yml`:

```yaml
# Extra caption appended to all posts
extra_caption: ' Please rate the Wallpaper #Wallpaper'

# Path to media list CSV file
media_list: config/media_list.csv

# Schedule configuration
schedule:
  # Morning window: 2 posts between 13:00-15:00
  - time: '13:00'
    window_hours: 2
    max_tasks: 2
  
  # Evening post at exactly 19:00
  - time: '19:00'
  
  # Night window: 1 post between 21:30-22:30
  - time: '21:30'
    window_hours: 1
```

Schedule configuration options:
- `time`: Required. Time in 24-hour format (HH:MM)
- `window_hours`: Optional. Hours after start time during which posts can be made
- `max_tasks`: Optional. Maximum posts in this window (default: 1)

### Media List Configuration

Create a CSV file (default: `config/media_list.csv`) with the following columns:
- `file_path`: Required. Full path to media file
- `caption`: Optional. Custom caption for the post. If not provided, an AI-generated caption will be used
- `_STATUS_`: Optional. Upload status (empty=pending, PROCESSED, ERROR)

Example:
```csv
file_path,caption,_STATUS_
/path/to/image1.jpg,Beautiful sunset,                  # Custom caption
/path/to/image2.jpg,,                                 # Will use AI-generated caption
/path/to/image3.jpg,Mountain view,PROCESSED           # Already processed
```

## Usage

### Scheduler Mode

Run the scheduler to automatically post media according to the schedule:

```bash
# Run in headless mode (default)
python run.py scheduler

# Run with browser UI visible
python run.py scheduler --no-headless

# Use custom config and media list
python run.py scheduler --config custom_config.yml --media-list custom_list.csv

# Add extra caption to all posts
python run.py scheduler --extra-caption "Follow me! #instagram"
```

### Single Upload Mode

Upload a single media file immediately:

```bash
# Basic upload with caption
python run.py insta-upload -f image.jpg -c "My caption"

# Add extra caption
python run.py insta-upload -f image.jpg -c "My caption" --extra-caption "#hashtags"

# Show browser UI
python run.py insta-upload -f image.jpg -c "My caption" --no-headless
```

### Caption Generation

Generate captions for images using BLIP:

```bash
# Generate for single image
python run.py generate-captions input.jpg

# Generate for directory of images
python run.py generate-captions /path/to/images/

# Specify output file
python run.py generate-captions input.jpg -o captions.csv
```

## Scheduler Operation

### Multiple Instances

The scheduler uses a lock file to prevent multiple instances from running simultaneously. If you try to start a second instance, you'll get an error:

```
ERROR: Another instance of scheduler is already running
INFO: If you are sure no other instance is running, you can manually delete the lock file:
INFO:     rm data/scheduler.lock
```

Only delete the lock file if you're certain no other scheduler instance is running.

### Window Tasks

The scheduler tracks tasks executed in each window using a JSON file (`data/window_tasks.json`). This ensures:
- Maximum posts per window is not exceeded
- Tasks aren't re-executed if scheduler is restarted within a window

### Status Tracking

Media upload status is tracked in the media list CSV:
- Empty or missing: Pending
- `PROCESSED`: Successfully uploaded
- `ERROR`: Upload failed

## Logging

Logs are written to:
- Console output
- `logs/instagram_uploader.log`

## Error Recovery

1. If scheduler crashes:
   - Check logs for error details
   - Verify no instance is running: `ps aux | grep scheduler`
   - Delete lock file if necessary: `rm data/scheduler.lock`
   - Restart scheduler

2. If upload fails:
   - Item is marked as ERROR in media list
   - Will be skipped in future runs
   - To retry, clear the status in media list CSV 