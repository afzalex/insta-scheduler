import pytest
from selenium.webdriver.remote.webdriver import WebDriver
from src.utils import retry_get_element
from src.exceptions import ElementNotFoundError

def test_retry_get_element_success(mock_driver):
    element = retry_get_element(mock_driver, "//test")
    assert element is not None

def test_retry_get_element_timeout(mock_driver):
    with pytest.raises(ElementNotFoundError):
        retry_get_element(mock_driver, "//nonexistent", timeoutseconds=1) 