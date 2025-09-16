#!/usr/bin/env python3
"""
FERC Tariff XML Downloader

This script automates the process of downloading XML files from the FERC tariff website.
It navigates through all pages, clicks on XML links, handles the export popup,
and downloads all XML files to a TariffXML folder.
"""

import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import config


class FERCTariffDownloader:
    def __init__(self, download_folder=None):
        """Initialize the downloader with configuration."""
        self.download_folder = os.path.abspath(download_folder or config.download_folder)
        self.base_url = config.base_url
        self.driver = None
        self.wait = None
        
        # Create download folder if it doesn't exist
        os.makedirs(self.download_folder, exist_ok=True)
        
        # Setup logging
        handlers = [logging.StreamHandler()]
        if config.log_to_file:
            handlers.append(logging.FileHandler(config.log_filename))
            
        logging.basicConfig(
            level=getattr(logging, config.log_level),
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=handlers
        )
        self.logger = logging.getLogger(__name__)
    
    def setup_driver(self):
        """Setup Chrome driver with download preferences."""
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument(f"--window-size={config.window_width},{config.window_height}")
        
        if config.headless:
            chrome_options.add_argument("--headless")
        
        # Set download preferences
        prefs = {
            "download.default_directory": self.download_folder,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        # Use webdriver-manager to automatically handle driver installation
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.wait = WebDriverWait(self.driver, config.popup_wait)
        self.logger.info("Chrome driver initialized")
    
    def get_total_pages(self):
        """Get the total number of pages from the pagination."""
        try:
            # Look for pagination elements
            pagination_elements = self.driver.find_elements(By.CSS_SELECTOR, ".pagination a, .pager a")
            if pagination_elements:
                # Get the last page number
                page_numbers = []
                for element in pagination_elements:
                    text = element.text.strip()
                    if text.isdigit():
                        page_numbers.append(int(text))
                return max(page_numbers) if page_numbers else 1
            return 1
        except Exception as e:
            self.logger.warning(f"Could not determine total pages: {e}")
            return 300  # Fallback to mentioned 300+ pages
    
    def handle_xml_export_popup(self):
        """Handle the XML export popup by selecting all status checkboxes and plain text XML."""
        try:
            self.logger.info("Handling XML export popup")
            
            # Wait for the popup to appear - try multiple possible selectors
            popup_selectors = [
                "#exportPopup",
                ".modal-dialog",
                ".popup",
                "[role='dialog']",
                ".export-dialog"
            ]
            
            popup = None
            for selector in popup_selectors:
                try:
                    popup = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    self.logger.info(f"Found popup with selector: {selector}")
                    break
                except TimeoutException:
                    continue
            
            if not popup:
                self.logger.warning("Could not find export popup")
                return
            
            # Find and check all status checkboxes - try multiple patterns
            checkbox_selectors = [
                "input[type='checkbox'][name*='status']",
                "input[type='checkbox'][id*='status']",
                "input[type='checkbox'][class*='status']",
                ".status-checkbox input[type='checkbox']",
                "input[type='checkbox']"  # fallback - all checkboxes
            ]
            
            status_checkboxes = []
            for selector in checkbox_selectors:
                checkboxes = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if checkboxes:
                    status_checkboxes = checkboxes
                    self.logger.info(f"Found {len(checkboxes)} checkboxes with selector: {selector}")
                    break
            
            # Check all found checkboxes
            for i, checkbox in enumerate(status_checkboxes):
                try:
                    if not checkbox.is_selected():
                        self.driver.execute_script("arguments[0].click();", checkbox)
                        time.sleep(0.1)
                        self.logger.debug(f"Checked checkbox {i+1}")
                except Exception as e:
                    self.logger.warning(f"Could not check checkbox {i+1}: {e}")
            
            # Select plain text XML format - try multiple patterns
            radio_selectors = [
                "input[type='radio'][value='plaintext']",
                "input[type='radio'][value*='plain']",
                "input[type='radio'][id*='plaintext']",
                "input[type='radio'][id*='plain']",
                ".format-option input[type='radio']"
            ]
            
            for selector in radio_selectors:
                try:
                    plain_text_radio = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if not plain_text_radio.is_selected():
                        self.driver.execute_script("arguments[0].click();", plain_text_radio)
                        self.logger.info(f"Selected plain text format with selector: {selector}")
                    break
                except NoSuchElementException:
                    continue
            
            # Click export button - try multiple patterns
            export_button_selectors = [
                "input[type='button'][value*='Export']",
                "input[type='submit'][value*='Export']", 
                "button[onclick*='export']",
                "button:contains('Export')",
                "#exportButton",
                ".export-btn",
                "input[id*='export']",
                "button[id*='export']"
            ]
            
            for selector in export_button_selectors:
                try:
                    export_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    self.driver.execute_script("arguments[0].click();", export_button)
                    self.logger.info(f"Clicked export button with selector: {selector}")
                    break
                except NoSuchElementException:
                    continue
            
            self.logger.info("XML export initiated")
            time.sleep(3)  # Wait for download to start
            
        except TimeoutException:
            self.logger.error("Timeout waiting for export popup")
        except Exception as e:
            self.logger.error(f"Error handling export popup: {e}")
    
    def download_xml_from_current_page(self):
        """Download XML files from the current page."""
        try:
            # Find all XML links on the current page - try multiple patterns
            xml_link_selectors = [
                "//a[contains(text(), 'XML')]",
                "//a[contains(@href, 'xml')]",
                "//a[contains(@href, 'XML')]",
                "//td[contains(@class, 'xml')]/a",
                "//td[contains(text(), 'XML')]/a",
                "//a[contains(@title, 'XML')]",
                "//a[contains(@onclick, 'xml')]"
            ]
            
            xml_links = []
            for selector in xml_link_selectors:
                try:
                    links = self.driver.find_elements(By.XPATH, selector)
                    if links:
                        xml_links = links
                        self.logger.info(f"Found {len(links)} XML links with selector: {selector}")
                        break
                except Exception as e:
                    self.logger.debug(f"Selector {selector} failed: {e}")
                    continue
            
            if not xml_links:
                self.logger.warning("No XML links found on current page")
                return
            
            self.logger.info(f"Processing {len(xml_links)} XML links on current page")
            
            for i, link in enumerate(xml_links):
                try:
                    self.logger.info(f"Clicking XML link {i+1}/{len(xml_links)}")
                    
                    # Scroll to the link to ensure it's visible
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", link)
                    time.sleep(0.5)
                    
                    # Click the XML link using JavaScript to avoid interception
                    self.driver.execute_script("arguments[0].click();", link)
                    
                    # Handle the export popup
                    self.handle_xml_export_popup()
                    
                    # Wait a bit before next download
                    time.sleep(2)
                    
                except Exception as e:
                    self.logger.error(f"Error with XML link {i+1}: {e}")
                    continue
        
        except Exception as e:
            self.logger.error(f"Error downloading XML from current page: {e}")
    
    def navigate_to_next_page(self):
        """Navigate to the next page if available."""
        try:
            # Look for "Next" button or pagination
            next_button = None
            
            # Try different selectors for next button
            next_selectors = [
                "a[title='Next']",
                "a[aria-label='Next']",
                "input[type='submit'][value*='Next']",
                ".pagination .next a",
                "a:contains('Next')"
            ]
            
            for selector in next_selectors:
                try:
                    next_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except NoSuchElementException:
                    continue
            
            if next_button and next_button.is_enabled():
                next_button.click()
                time.sleep(2)  # Wait for page to load
                return True
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"Error navigating to next page: {e}")
            return False
    
    def run(self):
        """Main method to run the downloader."""
        try:
            self.setup_driver()
            self.logger.info("Starting FERC Tariff XML download process")
            
            # Navigate to the initial page
            self.driver.get(self.base_url)
            time.sleep(3)
            
            # Get total pages
            total_pages = self.get_total_pages()
            self.logger.info(f"Estimated total pages: {total_pages}")
            
            page_number = 1
            while True:
                self.logger.info(f"Processing page {page_number}")
                
                # Download XML files from current page
                self.download_xml_from_current_page()
                
                # Try to navigate to next page
                if not self.navigate_to_next_page():
                    self.logger.info("No more pages to process")
                    break
                
                page_number += 1
                
                # Safety check to prevent infinite loop
                if page_number > total_pages + 10:
                    self.logger.warning("Reached safety limit, stopping")
                    break
            
            self.logger.info(f"Download process completed. Files saved to: {self.download_folder}")
            
        except Exception as e:
            self.logger.error(f"Fatal error during download process: {e}")
        
        finally:
            if self.driver:
                self.driver.quit()
                self.logger.info("Browser closed")


def main():
    """Main entry point."""
    downloader = FERCTariffDownloader()
    downloader.run()


if __name__ == "__main__":
    main()