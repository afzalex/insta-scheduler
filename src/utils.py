import os
import time
from prompt_toolkit import prompt
from prompt_toolkit.document import Document
from prompt_toolkit.key_binding import KeyBindings
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import logging
from typing import Union, List, Optional
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from contextlib import contextmanager


import os
import json
from pathlib import Path

def load_env_from_json():
    """Load environment variables from a JSON file"""
    env_file = Path('config/env_config.json')
    
    if not env_file.exists():
        # Create default config if doesn't exist
        default_config = {
            "INSTAGRAM_USERNAME": "",
            "INSTAGRAM_PASSWORD": "",
            "CHROME_DRIVER_PATH": "./chromedriver/windows/chromedriver.exe",
            "USER_DATA_DIR": "chrome_user_data"
        }
        with open(env_file, 'w') as f:
            json.dump(default_config, f, indent=4)
        print("Created default env_config.json file. Please fill in your credentials.")
        return default_config
    
    with open(env_file, 'r') as f:
        return json.load(f)

def set_environment_variables():
    """Set environment variables from config"""
    config = load_env_from_json()
    
    # Set each environment variable
    for key, value in config.items():
        os.environ[key] = value


# Read all data from config file into a variable
def get_config_data(config_file):
    """
    Read and return contents of a config file.
    """
    config_content = ""
    if os.path.exists(config_file):
        with open(config_file, "r") as file:
            config_content = file.read()
    # config_content = get_multiline_input("", config_content)
    return config_content

def get_multiline_input(prompt_text="Edit the text below:\n", default_text=""):
    """
    Get multiline input from user with prefilled text and Ctrl+D binding.
    
    Args:
        prompt_text (str): Text to display above the input area
        default_text (str): Pre-filled text to show in the input area
    
    Returns:
        str: The user's edited text
    """
    # Key binding to accept input when pressing Ctrl+D
    kb = KeyBindings()

    @kb.add('c-d')
    def _(event):
        "Accept the input when Ctrl+D is pressed."
        event.app.exit(result=event.app.current_buffer.text)

    # Show the prompt with prefilled text
    return prompt(
        prompt_text,
        default=default_text,
        multiline=True,
        key_bindings=kb
    )

def get_chrome_driver():
    """Set up and return a configured Chrome WebDriver instance"""
    chrome_options = Options()
    # Path to store Chrome user data (cookies, cache, etc.)
    user_data_dir = "data/chrome_user_data"  # You can change this to any directory
    chrome_options.add_argument(f"--user-data-dir={os.path.abspath(user_data_dir)}")
    chrome_options.add_argument("--start-maximized")
    # Optional: Disable notifications and automation messages
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-infobars") 
    chrome_options.add_argument("--disable-extensions")
    # chrome_options.add_argument("/home/ubuntu/instaworkshop/chrome-headless-shell-linux64/chrome-headless-shell")
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    # chrome_options.binary_location = "/home/ubuntu/instaworkshop/chrome-headless-shell-linux64/chrome-headless-shell"
    # service = Service("/usr/local/bin/chromedriver")  # Path to your ChromeDriver
    service = Service("./chromedriver/windows/chromedriver.exe")  # Path to your ChromeDriver
    return webdriver.Chrome(service=service, options=chrome_options)

def retry_get_element(
    driver: WebDriver, 
    xpaths: Union[str, List[str]], 
    timeoutseconds: int = 10
) -> WebElement:
    """
    Repeatedly tries to find an element by any of the provided xpaths.
    
    Args:
        driver: Selenium WebDriver instance
        xpaths: Single xpath string or list of xpath strings to locate the element
        timeoutseconds: Maximum time to wait in seconds
    
    Returns:
        WebElement: The first found element from the first matching xpath
        
    Raises:
        TimeoutException: If no elements found within timeout period
    """
    xpath_list = [xpaths] if isinstance(xpaths, str) else xpaths
    logger.debug(f"Looking for elements with xpaths: {xpath_list}")
    elapsed = 0
    while elapsed < timeoutseconds:
        for xpath in xpath_list:
            elements = driver.find_elements(By.XPATH, xpath)
            if elements:
                logger.debug(f"Found element with xpath: {xpath}")
                return elements[0]
        time.sleep(0.5)
        elapsed += 0.5
    logger.error(f"Could not find elements with xpaths: {xpath_list}")
    raise Exception(f"No elements found for any of the provided xpaths within {timeoutseconds} seconds")

def is_home_screen_displayed(driver):
    """Check if the Instagram home screen is displayed by looking for the Home button."""
    home_elements = driver.find_elements(By.XPATH, "//a[@role='link']//svg[@aria-label='Home']")
    return len(home_elements) > 0

def wait_for_element_to_disappear(driver: WebDriver, xpath: str, timeoutseconds: int = 10) -> None:
    """
    Waits for an element to disappear by checking the absence of the provided xpath.
    
    Args:
        driver: Selenium WebDriver instance
        xpath: XPath string to locate the element
        timeoutseconds: Maximum time to wait in seconds (default 10)
    
    Raises:
        Exception if the element does not disappear within the timeout period.
    """
    logger.debug(f"Waiting for element to disappear: {xpath}")
    elapsed = 0
    while elapsed < timeoutseconds:
        elements = driver.find_elements(By.XPATH, xpath)
        if not elements:
            logger.debug(f"Element disappeared: {xpath}")
            return
        time.sleep(0.5)
        elapsed += 0.5
    logger.error(f"Element did not disappear: {xpath}")
    raise Exception(f"Element with xpath '{xpath}' did not disappear within {timeoutseconds} seconds")

# Configure logging
def setup_logging():
    """Configure logging for the application"""
    # Create logs directory if it doesn't exist
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / 'instagram_uploader.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

@contextmanager
def managed_driver():
    """Context manager for the Chrome WebDriver"""
    driver = None
    try:
        driver = get_chrome_driver()
        yield driver
    finally:
        if driver:
            driver.quit()