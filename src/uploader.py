import os
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from src.utils import (
    get_config_data, 
    retry_get_element, 
    set_environment_variables, 
    get_chrome_driver,
    wait_for_element_to_disappear,
    managed_driver,
    logger,
    verify_file_exists,
    parse_arguments
)
from src.constants import *
from src.exceptions import InstagramUploaderError
from src.config import InstagramConfig
from pathlib import Path

def get_or_generate_caption(media_path: str, caption: str = None) -> str:
    """
    Get provided caption or generate one using BLIP
    
    Args:
        media_path: Path to media file
        caption: Optional provided caption
        
    Returns:
        str: Caption to use (generated or provided)
    """
    if caption:
        return caption
        
    try:
        from src.caption_generator import CaptionGenerator
        generator = CaptionGenerator()
        generated_caption = generator.generate_caption(media_path)
        logger.info(f"Generated caption: {generated_caption}")
        return generated_caption
    except Exception as e:
        logger.warning(f"Failed to generate caption: {e}")
        return None

def validate_upload_requirements(args, config):
    """
    Validate all requirements before starting the upload process
    
    Args:
        args: Command line arguments
        config: Instagram configuration (already validated)
        
    Raises:
        InstagramUploaderError: If any validation fails
    """
    # Get media path from args or config
    config_data = get_config_data("config/instagram_upload_config.txt")
    config_lines = config_data.strip().split('\n') if config_data else []
    
    # Use command line args if provided, otherwise use config file for media path
    post_media_path = args.file if args.file else (config_lines[0].strip() if len(config_lines) > 0 else "")
    
    if not post_media_path:
        raise InstagramUploaderError("No media file path provided")
    
    # Verify media file
    try:
        post_media_path = verify_file_exists(post_media_path)
    except (FileNotFoundError, PermissionError) as e:
        raise InstagramUploaderError(f"Media file error: {e}")
    
    # Handle caption with priority:
    # 1. Command line argument
    # 2. Generated caption
    # 3. Config file (fallback)
    post_caption = None
    
    # Check command line argument first
    if hasattr(args, 'caption') and args.caption:
        post_caption = args.caption
    else:
        # Try to generate caption
        post_caption = get_or_generate_caption(post_media_path)
        
        # If generation fails, try config file as last resort
        if not post_caption and len(config_lines) > 1 and config_lines[1].strip():
            post_caption = config_lines[1].strip()
            logger.info("Using caption from config file as fallback")
    
    # Append extra caption if provided
    if post_caption and hasattr(args, 'extra_caption') and args.extra_caption:
        post_caption = f"{post_caption}\n\n{args.extra_caption}"
        logger.info("Added extra caption to post")
            
    return post_media_path, post_caption

def main(args=None):
    try:
        logger.info("Starting Instagram upload process")
        if args is None:
            args = parse_arguments()
        
        # Load configuration
        try:
            config = InstagramConfig.from_json(Path("config/env_config.json"))
            logger.info("Configuration loaded successfully")
        except Exception as e:
            raise InstagramUploaderError(f"Failed to load configuration: {e}")
        
        # Validate all requirements before starting
        logger.info("Validating upload requirements")
        post_media_path, post_caption = validate_upload_requirements(args, config)
        logger.info("All requirements validated successfully")
        
        # Now proceed with the actual upload
        with managed_driver(headless=args.headless) as driver:
            logger.info("Navigating to Instagram login page")
            driver.get("https://www.instagram.com/accounts/login/")
            
            logger.info("Checking login status")
            retelement = retry_get_element(driver, [XPATH_HOME_ICON, XPATH_USERNAME_INPUT])

            if retelement.get_attribute("aria-label") == "Home":
                logger.info("Already logged in")
            else:
                logger.info("Login required, attempting login")
                logger.info("Submitting login credentials")
                retry_get_element(driver, "//input[@name='username']").send_keys(config.username)
                retry_get_element(driver, "//input[@name='password']").send_keys(config.password + Keys.RETURN)

                logger.info("Handling post-login prompts")
                try:
                    retry_get_element(driver, XPATH_NOT_NOW_BUTTON).click()
                    logger.info("Dismissed 'Save Login Info' prompt")
                except:
                    logger.debug("No 'Save Login Info' prompt found")

                try:
                    driver.find_element(By.XPATH, XPATH_NOT_NOW_BUTTON).click()
                    logger.info("Dismissed notifications prompt")
                except:
                    logger.debug("No notifications prompt found")
            
            logger.info("Initiating new post creation")
            retry_get_element(driver, XPATH_NEW_POST_BUTTON).click()

            logger.info("Uploading media file")
            retry_get_element(driver, XPATH_FILE_INPUT).send_keys(post_media_path)

            logger.info("Configuring post settings")
            retry_get_element(driver, XPATH_SELECT_CROP).click()
            retry_get_element(driver, XPATH_ORIGINAL_CROP).click()
            retry_get_element(driver, XPATH_NEXT_BUTTON).click()

            logger.info("Checking post type")
            heading_label = retry_get_element(driver, [XPATH_EDIT_HEADING, XPATH_NEW_REEL_HEADING])
            if heading_label.text == "Edit":
                logger.info("Edit Step found -- skipping")
                retry_get_element(driver, XPATH_NEXT_BUTTON).click()
            else:
                logger.info("New Post Step found -- posting media")

            logger.info("Adding caption")
            retry_get_element(driver, XPATH_CAPTION_INPUT).send_keys(post_caption)
            
            logger.info("Sharing post")
            retry_get_element(driver, XPATH_SHARE_BUTTON).click()

            logger.info("Waiting for upload completion")
            wait_for_element_to_disappear(driver, XPATH_NEW_REEL_HEADING)
            wait_for_element_to_disappear(driver, XPATH_REEL_SHARING_HEADING, 60)
            retry_get_element(driver, [XPATH_REEL_SHARED_HEADING, XPATH_POST_SHARED_HEADING])
            logger.info("Upload completed successfully")

    except InstagramUploaderError as e:
        logger.error(f"Instagram upload failed: {e}")
        return 1
    except Exception as e:
        logger.exception("Unexpected error occurred")
        return 1
    
    logger.info("Process completed successfully")
    return 0

if __name__ == "__main__":
    exit(main()) 