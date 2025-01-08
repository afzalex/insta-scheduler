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
    logger
)
from src.constants import *
from src.exceptions import InstagramUploaderError
from src.config import InstagramConfig
from pathlib import Path

def main():
    try:
        logger.info("Starting Instagram upload process")
        config = InstagramConfig.from_json(Path("config/env_config.json"))
        logger.info("Configuration loaded successfully")
        print(config)
        
        with managed_driver() as driver:
            logger.info("Navigating to Instagram login page")
            driver.get("https://www.instagram.com/accounts/login/")
            
            logger.info("Checking login status")
            retelement = retry_get_element(driver, [XPATH_HOME_ICON, XPATH_USERNAME_INPUT])

            if retelement.get_attribute("aria-label") == "Home":
                logger.info("Already logged in")
            else:
                logger.info("Login required, attempting login")
                username = config.username
                password = config.password

                if not username or not password:
                    logger.info("Credentials not found in environment, requesting manual input")
                    username = input("Enter your Instagram username: ").strip()
                    password = input("Enter your Instagram password: ").strip()
                
                logger.info("Submitting login credentials")
                retry_get_element(driver, "//input[@name='username']").send_keys(username)
                retry_get_element(driver, "//input[@name='password']").send_keys(password + Keys.RETURN)

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

            logger.info("Loading post configuration")
            config_data = get_config_data("config/instagram_upload_config.txt")
            config_lines = config_data.strip().split('\n')
            post_media_path = config_lines[0].strip() if len(config_lines) > 0 else ""
            post_caption = config_lines[1].strip() if len(config_lines) > 1 else ""
            logger.info(f"Media path: {post_media_path}")

            logger.info("Uploading media file")
            retry_get_element(driver, XPATH_FILE_INPUT).send_keys(post_media_path)

            logger.info("Configuring post settings")
            retry_get_element(driver, XPATH_SELECT_CROP).click()
            retry_get_element(driver, XPATH_ORIGINAL_CROP).click()
            retry_get_element(driver, XPATH_NEXT_BUTTON).click()

            logger.info("Checking post type")
            heading_label = retry_get_element(driver, [XPATH_EDIT_HEADING, XPATH_NEW_REEL_HEADING])
            if heading_label.text == "Edit":
                logger.info("Post type: Video")
                retry_get_element(driver, XPATH_NEXT_BUTTON).click()
            else:
                logger.info("Post type: Image")

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