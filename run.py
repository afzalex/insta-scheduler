import argparse
from src.uploader import main as uploader_main
from src.scheduler import main as scheduler_main

def parse_args():
    parser = argparse.ArgumentParser(description='Instagram Media Manager')
    parser.add_argument('--scheduler', action='store_true',
                       help='Run in scheduler mode')
    parser.add_argument('--headless', action='store_true',
                       help='Run in headless mode')
    
    # Single upload arguments
    parser.add_argument('-f', '--file', type=str,
                       help='Path to media file (for single upload)')
    parser.add_argument('-c', '--caption', type=str,
                       help='Caption for the post (for single upload)')
    
    # Scheduler arguments
    parser.add_argument('--media-list', type=str,
                       default='config/media_list.csv',
                       help='Path to media list CSV file (for scheduler)')
    parser.add_argument('--scheduler-config', type=str,
                       default='config/scheduler_config.yml',
                       help='Path to scheduler configuration YAML file')
    return parser.parse_args()

def main():
    args = parse_args()
    return scheduler_main(args.scheduler_config, args.media_list) if args.scheduler else uploader_main()

if __name__ == "__main__":
    exit(main()) 