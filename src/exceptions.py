class InstagramUploaderError(Exception):
    """Base exception for Instagram Uploader"""
    pass

class ElementNotFoundError(InstagramUploaderError):
    """Raised when an element cannot be found"""
    pass

class ElementNotDisappearError(InstagramUploaderError):
    """Raised when an element does not disappear within timeout"""
    pass

class ConfigurationError(InstagramUploaderError):
    """Raised when there's an issue with configuration"""
    pass 