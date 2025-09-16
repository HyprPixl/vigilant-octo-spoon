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
import re
from pathlib import Path
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
            summary = self.driver.find_element(By.CSS_SELECTOR, "b.dxp-summary").text
            match = re.search(r"Page\\s+\\d+\\s+of\\s+(\\d+)", summary)
            if match:
                return int(match.group(1))
            return 1
        except Exception as e:
            self.logger.warning(f"Could not determine total pages: {e}")
            return 300  # Fallback to mentioned 300+ pages

    def handle_xml_export_popup(self):
        """Handle the XML export popup by selecting all status checkboxes and plain text XML."""
        try:
            self.logger.info("Handling XML export popup")
            previous_files = self._list_downloaded_files()

            self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "GB_frame")))
            inner_locator = (By.CSS_SELECTOR, "iframe#GB_frame")
            WebDriverWait(self.driver, config.popup_wait).until(
                EC.frame_to_be_available_and_switch_to_it(inner_locator)
            )

            status_checkboxes = self.driver.find_elements(By.CSS_SELECTOR, "input[id^='Content1_lstStatus_']")
            for i, checkbox in enumerate(status_checkboxes):
                try:
                    if not checkbox.is_selected():
                        self.driver.execute_script("arguments[0].click();", checkbox)
                        time.sleep(config.checkbox_delay)
                        self.logger.debug(f"Checked status checkbox {i + 1}")
                except Exception as e:
                    self.logger.warning(f"Could not check checkbox {i + 1}: {e}")

            try:
                binary_checkbox = self.driver.find_element(By.ID, "Content1_lstBinaryText_0")
                if binary_checkbox.is_selected():
                    self.driver.execute_script("arguments[0].click();", binary_checkbox)
            except NoSuchElementException:
                self.logger.debug("Binary text checkbox not found")

            try:
                plain_checkbox = self.driver.find_element(By.ID, "Content1_lstBinaryText_1")
                if not plain_checkbox.is_selected():
                    self.driver.execute_script("arguments[0].click();", plain_checkbox)
                    self.logger.info("Selected plain text format")
            except NoSuchElementException:
                self.logger.warning("Plain text checkbox not found")

            try:
                export_button = WebDriverWait(self.driver, config.popup_wait).until(
                    EC.element_to_be_clickable((By.ID, "Content1_btnExport"))
                )
                self.driver.execute_script("arguments[0].click();", export_button)
                self.logger.info("XML export initiated")
            except TimeoutException:
                self.logger.error("Export button not clickable")
                return

            no_data_message = False
            try:
                WebDriverWait(self.driver, config.no_data_wait).until(
                    EC.text_to_be_present_in_element(
                        (By.ID, "Content1_ExceededMaxlbl"),
                        "No data section has been identified"
                    )
                )
                no_data_message = True
                self.logger.warning("No data available for current tariff selection")
            except TimeoutException:
                pass

            self.driver.switch_to.default_content()
            if not no_data_message:
                self._wait_for_download(previous_files)

            try:
                self.driver.execute_script("if (typeof GB_hide === 'function') GB_hide();")
                WebDriverWait(self.driver, config.popup_wait).until(
                    EC.invisibility_of_element_located((By.ID, "GB_window"))
                )
            except TimeoutException:
                self.logger.warning("Export popup did not close as expected")
            time.sleep(1)

        except TimeoutException:
            self.logger.error("Timeout waiting for export popup")
        except Exception as e:
            self.logger.error(f"Error handling export popup: {e}")

    def _list_downloaded_files(self):
        return {path for path in os.listdir(self.download_folder) if path.endswith(".xml")}

    def _wait_for_download(self, previous_files):
        start_time = time.time()
        download_path = Path(self.download_folder)
        while time.time() - start_time < config.download_timeout:
            current_files = self._list_downloaded_files()
            partial_files = list(download_path.glob("*.crdownload"))
            if len(current_files) > len(previous_files) and not partial_files:
                return
            time.sleep(0.5)
        self.logger.warning("Download wait timeout reached")

    def download_xml_from_current_page(self, page_number):
        """Download XML files from the current page."""
        try:
            self.wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.gridLink[title='Export XML']")))
            xml_links = self.driver.find_elements(By.CSS_SELECTOR, "a.gridLink[title='Export XML']")
            if not xml_links:
                self.logger.warning("No XML links found on current page")
                return
            
            self.logger.info(f"Processing {len(xml_links)} XML links on page {page_number}")
            
            for index in range(len(xml_links)):
                try:
                    current_links = self.driver.find_elements(By.CSS_SELECTOR, "a.gridLink[title='Export XML']")
                    if index >= len(current_links):
                        break
                    link = current_links[index]
                    href = link.get_attribute("href") or ""
                    tid_match = re.search(r"tid=(\d+)", href, re.IGNORECASE)
                    if tid_match:
                        expected_name = f"Tariff_{tid_match.group(1)}.xml"
                        if Path(self.download_folder, expected_name).exists():
                            self.logger.info(f"Skipping {expected_name} (already downloaded)")
                            continue
                    self.logger.info(f"Clicking XML link {index + 1}/{len(xml_links)} on page {page_number}")
                    
                    # Scroll to the link to ensure it's visible
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", link)
                    time.sleep(0.5)
                    
                    # Click the XML link using JavaScript to avoid interception
                    self.driver.execute_script("arguments[0].click();", link)
                    
                    # Handle the export popup
                    self.handle_xml_export_popup()
                    
                    # Wait a bit before next download
                    time.sleep(config.download_wait)
                    
                except Exception as e:
                    self.logger.error(f"Error with XML link {index + 1}: {e}")
                    continue
        
        except Exception as e:
            self.logger.error(f"Error downloading XML from current page: {e}")

    def navigate_to_next_page(self):
        """Navigate to the next page if available."""
        try:
            self.wait_for_grid_ready()
            summary_element = self.driver.find_element(By.CSS_SELECTOR, "b.dxp-summary")
            current_summary = summary_element.text

            next_locators = [
                (By.ID, "Content1_dxgrdTariffs_DXPagerTop_PBN"),
                (By.ID, "Content1_dxgrdTariffs_DXPagerBottom_PBN")
            ]

            next_button = None
            for by, value in next_locators:
                try:
                    candidate = self.driver.find_element(by, value)
                    if candidate.is_displayed() and "dxp-disabledButton" not in candidate.get_attribute("class"):
                        next_button = candidate
                        break
                except NoSuchElementException:
                    continue

            if not next_button:
                return False

            self.driver.execute_script("arguments[0].click();", next_button)
            WebDriverWait(self.driver, config.page_load_timeout).until(
                lambda d: d.find_element(By.CSS_SELECTOR, "b.dxp-summary").text != current_summary
            )
            self.wait_for_grid_ready()
            return True
                
        except Exception as e:
            self.logger.error(f"Error navigating to next page: {e}")
            return False

    def wait_for_grid_ready(self):
        try:
            loading_locator = (By.ID, "Content1_dxgrdTariffs_LP")
            WebDriverWait(self.driver, config.page_load_timeout).until(
                EC.invisibility_of_element_located(loading_locator)
            )
        except TimeoutException:
            self.logger.debug("Grid loading indicator did not disappear in time")
        self.wait.until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.gridLink[title='Export XML']"))
        )

    def open_all_tariffs(self):
        try:
            button = WebDriverWait(self.driver, config.page_load_timeout).until(
                EC.element_to_be_clickable((By.ID, "Content1_btnAll"))
            )
            button.click()
            self.wait_for_grid_ready()
        except TimeoutException:
            self.logger.error("Could not load tariff list")

    def run(self):
        """Main method to run the downloader."""
        try:
            self.setup_driver()
            self.logger.info("Starting FERC Tariff XML download process")
            
            # Navigate to the initial page
            self.driver.get(self.base_url)
            time.sleep(config.page_load_wait)
            self.open_all_tariffs()
            
            # Get total pages
            total_pages = self.get_total_pages()
            self.logger.info(f"Estimated total pages: {total_pages}")
            
            page_number = 1
            while True:
                self.logger.info(f"Processing page {page_number}")
                
                # Download XML files from current page
                self.download_xml_from_current_page(page_number)
                
                # Try to navigate to next page
                if not self.navigate_to_next_page():
                    self.logger.info("No more pages to process")
                    break
                
                page_number += 1

                # Safety check to prevent infinite loop
                if page_number > total_pages + 10:
                    self.logger.warning("Reached safety limit, stopping")
                    break
                if config.max_pages and page_number > config.max_pages:
                    self.logger.warning("Reached configured max_pages limit, stopping")
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
