from PIL import Image
import torch
import torch.version
from transformers import BlipProcessor, BlipForConditionalGeneration
from pathlib import Path
import logging
import csv
import sys
from typing import Iterator, Tuple
import argparse

logger = logging.getLogger(__name__)

class CaptionGenerator:
    def __init__(self):
        """Initialize BLIP model and processor"""
        try:
            logger.info("Loading BLIP model and processor")
            self.processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
            self.model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
            
            # Check CUDA availability and set device
            if torch.cuda.is_available():
                self.device = torch.device("cuda")
                # Log GPU info
                gpu_name = torch.cuda.get_device_name(0)
                gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1e9  # Convert to GB
                logger.info(f"Using GPU: {gpu_name} ({gpu_memory:.2f} GB)")
                
                # Move model to GPU and optimize for inference
                self.model = self.model.to(self.device)
                self.model = self.model.eval()  # Set to evaluation mode
                torch.cuda.empty_cache()  # Clear GPU cache
            else:
                self.device = torch.device("cpu")
                logger.warning("CUDA not available, using CPU for inference")
                
            logger.info(f"Model loaded successfully (using {self.device})")
        except Exception as e:
            logger.error(f"Failed to load BLIP model: {e}")
            raise

    def process_directory(self, directory_path: str) -> Iterator[Tuple[str, str]]:
        """
        Process all images in a directory
        
        Args:
            directory_path: Path to directory containing images
            
        Yields:
            Tuple[str, str]: (image_path, caption) for each image
        """
        path = Path(directory_path)
        if not path.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory_path}")
            
        # Common image extensions
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp'}
        
        # Process each image file
        for file_path in path.iterdir():
            if file_path.suffix.lower() in image_extensions:
                try:
                    caption = self.generate_caption(str(file_path))
                    yield str(file_path), caption
                except Exception as e:
                    logger.error(f"Failed to process {file_path}: {e}")
                    yield str(file_path), f"ERROR: {str(e)}"

    def generate_caption(self, image_path: str, max_length: int = 30) -> str:
        """Generate caption for single image"""
        try:
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
            logger.info(f"Generated caption for {image_path}: {caption}")
            return caption
            
        except Exception as e:
            logger.error(f"Failed to generate caption: {e}")
            raise

def generate_captions(input_path: str, output_file: str = 'captions.csv') -> int:
    """
    Generate captions for images and save to CSV
    
    Args:
        input_path: Path to image file or directory
        output_file: Path to output CSV file
        
    Returns:
        int: 0 for success, 1 for error
    """
    try:
        generator = CaptionGenerator()
        path = Path(input_path)
        
        with open(output_file, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['file_path', 'caption'])
            
            if path.is_dir():
                for image_path, caption in generator.process_directory(input_path):
                    writer.writerow([image_path, caption])
                    print(f"{image_path},{caption}")
            else:
                try:
                    caption = generator.generate_caption(input_path)
                    writer.writerow([input_path, caption])
                    print(f"{input_path},{caption}")
                except Exception as e:
                    writer.writerow([input_path, f"ERROR: {str(e)}"])
                    print(f"{input_path},ERROR: {str(e)}")
        
        print(f"\nCaptions saved to: {output_file}")
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
    parser.add_argument('--output', type=str, default='captions.csv',
                       help='Output CSV file path (default: captions.csv)')
    args = parser.parse_args()
    
    return generate_captions(args.path, args.output)

if __name__ == "__main__":
    exit(main()) 