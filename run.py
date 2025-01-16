import argparse
from src.uploader import main as uploader_main
from src.scheduler import main as scheduler_main
from src.caption_generator import generate_captions
import logging
import sys
logger = logging.getLogger(__name__)

def parse_args():
    parser = argparse.ArgumentParser(description='Instagram Media Manager')
    subparsers = parser.add_subparsers(dest='command', required=True,
                                    help='Commands')
    
    # Instagram Upload command
    upload_parser = subparsers.add_parser('insta-upload', help='Upload media to Instagram')
    upload_parser.add_argument('-f', '--file', type=str, required=True,
                           help='Path to media file')
    upload_parser.add_argument('-c', '--caption', type=str,
                           help='Caption for the post')
    upload_parser.add_argument('--extra-caption', type=str,
                           help='Additional text to append to caption')
    upload_parser.add_argument('--no-headless', action='store_true',
                           help='Run with browser UI (default: headless)')
    
    # Scheduler command
    scheduler_parser = subparsers.add_parser('scheduler', help='Run scheduler for automated uploads')
    scheduler_parser.add_argument('--media-list', type=str,
                              default='config/media_list.csv',
                              help='Path to media list CSV file')
    scheduler_parser.add_argument('--config', type=str,
                              default='config/scheduler_config.yml',
                              help='Path to scheduler configuration YAML file')
    scheduler_parser.add_argument('--no-headless', action='store_true',
                              help='Run with browser UI (default: headless)')
    scheduler_parser.add_argument('--extra-caption', type=str,
                              help='Additional text to append to all captions')
    
    # Caption generator command
    caption_parser = subparsers.add_parser('generate-captions', help='Generate captions for images')
    caption_parser.add_argument('input', type=str,
                            help='Path to image file or directory')
    caption_parser.add_argument('-o', '--output', type=str,
                            default='captions.csv',
                            help='Output CSV file path')
    
    # If no arguments at all, show main help
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
    
    # If only command is provided, show command-specific help
    if len(sys.argv) == 2:
        if sys.argv[1] == 'insta-upload':
            upload_parser.print_help()
        elif sys.argv[1] == 'scheduler':
            scheduler_parser.print_help()
        elif sys.argv[1] == 'generate-captions':
            caption_parser.print_help()
        sys.exit(1)
    
    return parser.parse_args()

def main(args=None):
    """
    Main entry point that can be called programmatically or from command line
    
    Args:
        args: Namespace object with arguments. If None, parse from command line
    """
    if args is None:
        args = parse_args()
    
    if args.command == 'generate-captions':
        return generate_captions(
            input_path=args.input,
            output_file=args.output
        )
    elif args.command == 'scheduler':
        # If extra_caption provided in command line, update config
        if hasattr(args, 'extra_caption') and args.extra_caption:
            import yaml
            with open(args.config) as f:
                config = yaml.safe_load(f)
            config['extra_caption'] = args.extra_caption
            with open(args.config, 'w') as f:
                yaml.dump(config, f)
        
        return scheduler_main(args.config, args.media_list, not args.no_headless)
    else:  # insta-upload
        # Create a new Namespace with uploader arguments
        upload_args = argparse.Namespace(
            file=args.file,
            caption=args.caption if hasattr(args, 'caption') else None,
            extra_caption=args.extra_caption if hasattr(args, 'extra_caption') else None,
            headless=not args.no_headless
        )
        return uploader_main(upload_args)

if __name__ == "__main__":
    exit(main()) 