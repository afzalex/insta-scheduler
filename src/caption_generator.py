from PIL import Image
from pathlib import Path
import logging
import csv
import sys
from typing import Iterator, Tuple
import argparse
import tempfile
import os

logger = logging.getLogger(__name__)

class CaptionGenerator:
    def __init__(self):
        """Initialize basic attributes"""
        self.processor = None
        self.model = None
        self.whisper_model = None
        self.device = None

    def _init_image_model(self):
        """Lazy initialization of BLIP model"""
        if self.model is None:
            try:
                logger.info("Loading BLIP model and processor")
                from transformers import BlipProcessor, BlipForConditionalGeneration
                self.processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
                self.model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
                
                # Set up device
                self._setup_device()
                
                # Move model to device and optimize
                self.model = self.model.to(self.device)
                self.model = self.model.eval()
                
                logger.info("BLIP model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load BLIP model: {e}")
                raise

    def _init_video_model(self):
        """Lazy initialization of Whisper model"""
        if self.whisper_model is None:
            try:
                logger.info("Loading Whisper model")
                import whisper
                import torch
                import warnings
                # Suppress the FutureWarning about weights_only
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=FutureWarning)
                    self.whisper_model = whisper.load_model("base")
                logger.info("Whisper model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load Whisper model: {e}")
                raise

    def _setup_device(self):
        """Set up the device (CPU/GPU)"""
        if self.device is None:
            import torch
            if torch.cuda.is_available():
                self.device = torch.device("cuda")
                # Log GPU info
                gpu_name = torch.cuda.get_device_name(0)
                gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1e9
                logger.info(f"Using GPU: {gpu_name} ({gpu_memory:.2f} GB)")
                torch.cuda.empty_cache()
            else:
                self.device = torch.device("cpu")
                logger.warning("CUDA not available, using CPU for inference")

    def process_directory(self, directory_path: str) -> Iterator[Tuple[str, str]]:
        """
        Process all images and videos in a directory
        
        Args:
            directory_path: Path to directory containing media files
            
        Yields:
            Tuple[str, str]: (file_path, caption) for each file
        """
        path = Path(directory_path)
        if not path.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory_path}")
            
        # Common media extensions
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp'}
        video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}
        
        # Process each file
        for file_path in path.iterdir():
            ext = file_path.suffix.lower()
            try:
                if ext in image_extensions:
                    caption = self.generate_image_caption(str(file_path))
                elif ext in video_extensions:
                    caption = self.generate_video_caption(str(file_path))
                else:
                    continue  # Skip unsupported files
                yield str(file_path), caption
            except Exception as e:
                logger.error(f"Failed to process {file_path}: {e}")
                yield str(file_path), f"ERROR: {str(e)}"

    def generate_image_caption(self, image_path: str, max_length: int = 30) -> str:
        """Generate caption for an image"""
        try:
            # Initialize BLIP model if not already done
            self._init_image_model()
            
            path = Path(image_path)
            if not path.exists():
                raise FileNotFoundError(f"Image not found: {image_path}")
            
            image = Image.open(image_path).convert('RGB')
            inputs = self.processor(image, return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_length=max_length,
                    num_beams=5,
                    temperature=1.0,
                    repetition_penalty=1.5
                )
            
            caption = self.processor.decode(outputs[0], skip_special_tokens=True)
            logger.debug(f"Generated image caption for {image_path}: {caption}")
            return caption
            
        except Exception as e:
            logger.error(f"Failed to generate image caption: {e}")
            raise

    def generate_video_caption(self, video_path: str) -> str:
        """Generate caption for a video by transcribing its audio"""
        try:
            # Initialize Whisper model if not already done
            self._init_video_model()
            
            path = Path(video_path)
            if not path.exists():
                raise FileNotFoundError(f"Video not found: {video_path}")

            # Create a temporary directory for audio extraction
            with tempfile.TemporaryDirectory() as temp_dir:
                audio_path = os.path.join(temp_dir, "audio.wav")
                
                # Extract audio from video
                logger.debug(f"Extracting audio from {video_path}")
                from moviepy.editor import VideoFileClip
                video = VideoFileClip(video_path)
                video.audio.write_audiofile(audio_path, logger=None)
                video.close()
                
                # Transcribe audio
                logger.debug("Transcribing audio")
                result = self.whisper_model.transcribe(audio_path)
                text = result["text"].strip()
                
                # Get first 10 words
                words = text.split()[:10]
                caption = " ".join(words)
                
                logger.debug(f"Generated video caption for {video_path}: {caption}")
                return caption

        except Exception as e:
            logger.error(f"Failed to generate video caption: {e}")
            raise

    def generate_caption(self, file_path: str, max_length: int = 30) -> str:
        """Generate caption for a media file (image or video)"""
        ext = Path(file_path).suffix.lower()
        video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}
        
        if ext in video_extensions:
            return self.generate_video_caption(file_path)
        else:
            return self.generate_image_caption(file_path, max_length)

def generate_captions(input_path: str, output_file: str = None) -> int:
    """
    Generate captions for images and optionally save to CSV
    
    Args:
        input_path: Path to image file or directory
        output_file: Optional path to output CSV file. If None, only print to console.
        
    Returns:
        int: 0 for success, 1 for error
    """
    try:
        generator = CaptionGenerator()
        path = Path(input_path)
        
        # Initialize CSV writer if output file is specified
        csv_writer = None
        csv_file = None
        if output_file:
            csv_file = open(output_file, 'w', newline='')
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(['file_path', 'caption'])
            logger.info(f"Writing captions to: {output_file}")
            
        try:
            if path.is_dir():
                for file_path, caption in generator.process_directory(input_path):
                    result = f"{file_path},{caption}"
                    print(result)
                    if csv_writer:
                        csv_writer.writerow([file_path, caption])
            else:
                try:
                    caption = generator.generate_caption(input_path)
                    result = f"{input_path},{caption}"
                    print(result)
                    if csv_writer:
                        csv_writer.writerow([input_path, caption])
                except Exception as e:
                    error_msg = f"ERROR: {str(e)}"
                    result = f"{input_path},{error_msg}"
                    print(result)
                    if csv_writer:
                        csv_writer.writerow([input_path, error_msg])
        finally:
            if csv_file:
                csv_file.close()
                logger.info(f"Captions saved to: {output_file}")
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description='Generate image captions using BLIP')
    parser.add_argument('path', type=str, 
                       help='Path to image file or directory of images')
    parser.add_argument('--max-length', type=int, default=30,
                       help='Maximum length of generated caption')
    parser.add_argument('-o', '--output', type=str,
                       help='Output CSV file path (optional)')
    args = parser.parse_args()
    
    return generate_captions(args.path, args.output)

if __name__ == "__main__":
    exit(main()) 