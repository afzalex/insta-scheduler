import os
from pathlib import Path
from dataclasses import dataclass

@dataclass
class InstagramConfig:
    username: str
    password: str
    
    @classmethod
    def from_json(cls, config_path: Path):
        """
        Create config from JSON file, with environment variables taking precedence
        
        Args:
            config_path: Path to config JSON file
            
        Returns:
            InstagramConfig: Configuration instance
        """
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
            
        import json
        with open(config_path) as f:
            config = json.load(f)
            
        return cls(
            # Environment variables take precedence over config file
            username=os.getenv('INSTAGRAM_USERNAME') or config.get('INSTAGRAM_USERNAME', ''),
            password=os.getenv('INSTAGRAM_PASSWORD') or config.get('INSTAGRAM_PASSWORD', '')
        )
        
    def validate(self):
        """Validate the configuration"""
        if not self.username:
            raise ValueError("Instagram username not configured")
        if not self.password:
            raise ValueError("Instagram password not configured") 