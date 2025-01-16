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

def validate_upload_requirements(args, config):
    """
    Validate all requirements before starting the upload process
    
    Args:
        args: Command line arguments
        config: Instagram configuration (already validated)
        
    Raises:
        InstagramUploaderError: If any validation fails
    """
    # Get media path and caption
    config_data = get_config_data("config/instagram_upload_config.txt")
    config_lines = config_data.strip().split('\n') if config_data else []
    
    # Use command line args if provided, otherwise use config file
    post_media_path = args.file if args.file else (config_lines[0].strip() if len(config_lines) > 0 else "")
    post_caption = args.caption if args.caption else (config_lines[1].strip() if len(config_lines) > 1 else "")
    
    if not post_media_path:
        raise InstagramUploaderError("No media file path provided")
    
    # Verify media file
    try:
        post_media_path = verify_file_exists(post_media_path)
    except (FileNotFoundError, PermissionError) as e:
        raise InstagramUploaderError(f"Media file error: {e}")
        
    # Check if caption is provided (optional, but log a warning)
    if not post_caption:
        logger.warning("No caption provided for the post")
        
    return post_media_path, post_caption

def main():
    try:
        logger.info("Starting Instagram upload process")
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