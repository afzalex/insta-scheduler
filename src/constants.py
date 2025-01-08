# XPath Selectors
XPATH_USERNAME_INPUT = "//input[@name='username']"
XPATH_PASSWORD_INPUT = "//input[@name='password']"
XPATH_HOME_ICON = "//*[@role='img' and contains(@aria-label, 'Home')]"
XPATH_NOT_NOW_BUTTON = "//div[@role='button' and text()='Not now']"

# Post Creation XPaths
XPATH_NEW_POST_BUTTON = "//*[@aria-label='New post' and not(ancestor::div[@style='display:none'])]"
XPATH_FILE_INPUT = "//input[@type='file']"
XPATH_SELECT_CROP = "//*[@role='img' and @aria-label='Select crop']"
XPATH_ORIGINAL_CROP = "//div[@role='button']//span[text()='Original']"
XPATH_NEXT_BUTTON = "//div[@role='button' and text()='Next']"
XPATH_EDIT_HEADING = "//div[@role='heading' and text()='Edit']"
XPATH_NEW_REEL_HEADING = "//div[@role='heading' and text()='New reel']"
XPATH_REEL_SHARING_HEADING = "//div[@role='heading' and text()='Sharing']"
XPATH_REEL_SHARED_HEADING = "//div[@role='heading' and text()='Reel shared']"
XPATH_CAPTION_INPUT = "//div[@aria-label='Write a caption...']"
XPATH_SHARE_BUTTON = "//div[@role='button' and text()='Share']"

# File Paths
FILE_INSTAGRAM_CONFIG = "instagram_upload_config.txt"
FILE_ENV_CONFIG = "env_config.json"

# Message Strings
MSG_LOGIN_DETECTED = "Login screen detected. Proceeding with login."
MSG_ALREADY_LOGGED = "Already logged in."
MSG_UPLOAD_SUCCESS = "Image uploaded successfully!" 