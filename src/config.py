from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import json
from src.exceptions import ConfigurationError

@dataclass
class InstagramConfig:
    username: str
    password: str
    chrome_driver_path: Path
    user_data_dir: Path
    
    @classmethod
    def from_json(cls, filepath: Path) -> 'InstagramConfig':
        """Create config from JSON file"""
        if not filepath.exists():
            raise ConfigurationError(f"Config file not found: {filepath}")
        
        with open(filepath) as f:
            data = json.load(f)
            
        return cls(
            username=data.get("INSTAGRAM_USERNAME", ""),
            password=data.get("INSTAGRAM_PASSWORD", ""),
            chrome_driver_path=Path(data.get("CHROME_DRIVER_PATH", "")),
            user_data_dir=Path(data.get("USER_DATA_DIR", ""))
        ) 