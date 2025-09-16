#!/usr/bin/env python3
"""FERC Tariff XML Downloader (hybrid implementation).

Selenium drives the DevExpress grid just enough to enumerate every tariff id,
then plain HTTP requests fetch the XML export for each id.  This keeps
pagination reliable while still performing the downloads without browser
automation overhead.
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Dict, Iterable, Optional, Set

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

import config

LIST_URL = config.base_url
EXPORT_URL = "https://etariff.ferc.gov/TariffExport.aspx?tid={tid}"

# Export dialog fields
STATUSES = [
    "ctl00$Content1$lstStatus$0",  # Effective
    "ctl00$Content1$lstStatus$1",  # Accepted
    "ctl00$Content1$lstStatus$2",  # Suspended
    "ctl00$Content1$lstStatus$3",  # Pending
    "ctl00$Content1$lstStatus$4",  # Conditionally Accepted
    "ctl00$Content1$lstStatus$5",  # Conditionally Effective
    "ctl00$Content1$lstStatus$6",  # Tolled
]
PLAIN_TEXT_FIELD = "ctl00$Content1$lstBinaryText$1"
EVENT_TARGET_EXPORT = "ctl00$Content1$btnExport"

# UI identifiers
EXTERNAL_PAGER_NEXT_ID = "Content1_dxgrdTariffs_DXPagerBottom_PBN"
GRID_EXPORT_LINK_SELECTOR = "a.gridLink[title='Export XML']"
GRID_LOADING_PANEL_ID = "Content1_dxgrdTariffs_LP"
ALL_TARIFFS_BUTTON_ID = "Content1_btnAll"


class FERCTariffDownloader:
    """Downloader that uses Selenium for pagination and requests for exports."""

    export_sleep: float = 0.15
    request_timeout: int = 60

    def __init__(
        self,
        download_folder: Optional[str] = None,
        max_pages: Optional[int] = None,
        max_files: Optional[int] = None,
    ) -> None:
        raw_download = Path(download_folder or config.download_folder)
        self.download_folder = raw_download
        self.output_dir = self._resolve_output_path(raw_download)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.max_pages = max_pages if max_pages is not None else config.max_pages
        self.max_files = max_files
        self.retry_attempts = getattr(config, "retry_attempts", 3)
        self.page_load_wait = getattr(config, "page_load_wait", 3)
        self.selenium_timeout = getattr(config, "page_load_timeout", 30)
        self.headless = getattr(config, "headless", False)
        self.window_width = getattr(config, "window_width", 1280)
        self.window_height = getattr(config, "window_height", 720)

        handlers = [logging.StreamHandler()]
        if getattr(config, "log_to_file", False):
            handlers.append(logging.FileHandler(config.log_filename))

        log_level_name = getattr(config, "log_level", "INFO")
        logging.basicConfig(
            level=getattr(logging, str(log_level_name).upper(), logging.INFO),
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=handlers,
        )
        self.logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _user_agent() -> str:
        return (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )

    @staticmethod
    def _to_soup(html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "html.parser")

    @staticmethod
    def _extract_inputs(soup: BeautifulSoup) -> Dict[str, str]:
        data: Dict[str, str] = {}
        for field in soup.find_all("input"):
            name = field.get("name")
            if name:
                data[name] = field.get("value", "")
        return data

    @staticmethod
    def _resolve_output_path(path: Path) -> Path:
        """Databricks-friendly path remapping."""
        text = str(path)
        if text.startswith("dbfs:/"):
            return Path("/dbfs/" + text[len("dbfs:/") :].lstrip("/"))
        return path.resolve()

    def _session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update({
            "User-Agent": self._user_agent(),
            "Referer": LIST_URL,
        })
        return session

    # ------------------------------------------------------------------
    # Selenium helpers
    # ------------------------------------------------------------------
    def _build_driver(self) -> webdriver.Chrome:
        options = Options()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument(f"--window-size={self.window_width},{self.window_height}")
        if self.headless:
            options.add_argument("--headless=new")

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(self.selenium_timeout)
        return driver

    def _wait_for_grid_ready(self, driver: webdriver.Chrome, wait: WebDriverWait) -> None:
        try:
            wait.until(EC.invisibility_of_element_located((By.ID, GRID_LOADING_PANEL_ID)))
        except TimeoutException:
            self.logger.debug("Grid loading indicator still visible; continuing")
        try:
            wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, GRID_EXPORT_LINK_SELECTOR)))
        except TimeoutException:
            self.logger.warning("No XML links detected after waiting for the grid")

    def _click_all_tariffs(self, driver: webdriver.Chrome, wait: WebDriverWait) -> None:
        try:
            button = wait.until(EC.element_to_be_clickable((By.ID, ALL_TARIFFS_BUTTON_ID)))
            driver.execute_script("arguments[0].click();", button)
        except TimeoutException as exc:  # pragma: no cover - live site interaction
            raise RuntimeError("Unable to activate 'All Tariffs' view") from exc

    @staticmethod
    def _extract_tids_from_elements(elements: Iterable[WebElement]) -> Set[str]:
        tids: Set[str] = set()
        for element in elements:
            try:
                href = element.get_attribute("href") or ""
            except StaleElementReferenceException:
                continue
            match = re.search(r"tid=(\d+)", href)
            if match:
                tids.add(match.group(1))
        return tids

    @staticmethod
    def _summary_changed(driver: webdriver.Chrome, selector: str, previous: str) -> bool:
        try:
            return driver.find_element(By.CSS_SELECTOR, selector).text != previous
        except (NoSuchElementException, StaleElementReferenceException):
            return True

    # ------------------------------------------------------------------
    # Core workflows
    # ------------------------------------------------------------------
    def collect_tariff_ids(self) -> Set[str]:
        tids: Set[str] = set()
        driver = self._build_driver()
        wait = WebDriverWait(driver, self.selenium_timeout)
        summary_selector = "b.dxp-summary"

        try:
            self.logger.debug("Opening tariff list page %s", LIST_URL)
            driver.get(LIST_URL)
            time.sleep(self.page_load_wait)

            self._click_all_tariffs(driver, wait)
            time.sleep(max(self.page_load_wait / 2, 0.5))

            page_index = 1
            while True:
                try:
                    self._wait_for_grid_ready(driver, wait)
                    links = driver.find_elements(By.CSS_SELECTOR, GRID_EXPORT_LINK_SELECTOR)
                    page_tids = self._extract_tids_from_elements(links)

                    if page_tids:
                        before = len(tids)
                        tids.update(page_tids)
                        self.logger.info(
                            "Collected %d ids from page %d (total=%d)",
                            len(page_tids),
                            page_index,
                            len(tids),
                        )
                        if len(tids) == before and page_index > 1:
                            self.logger.debug("No new ids found on page %d", page_index)
                    else:
                        self.logger.warning("No XML links detected on page %d", page_index)

                    if self.max_pages is not None and page_index >= self.max_pages:
                        break

                    try:
                        next_button = driver.find_element(By.ID, EXTERNAL_PAGER_NEXT_ID)
                    except NoSuchElementException:
                        break

                    classes = next_button.get_attribute("class") or ""
                    if "dxp-disabledButton" in classes:
                        break

                    try:
                        previous_summary = driver.find_element(By.CSS_SELECTOR, summary_selector).text
                    except NoSuchElementException:
                        previous_summary = str(page_index)

                    driver.execute_script("arguments[0].click();", next_button)

                    try:
                        wait.until(
                            lambda d: self._summary_changed(d, summary_selector, previous_summary)
                        )
                    except TimeoutException:
                        self.logger.warning(
                            "Timed out waiting to advance past page %d", page_index
                        )
                        break

                    page_index += 1
                except StaleElementReferenceException:
                    self.logger.debug(
                        "Stale element encountered on page %d; retrying after short pause",
                        page_index,
                    )
                    time.sleep(0.5)
                    continue

            return tids
        finally:
            driver.quit()

    def download_tariff_xml(self, tid: str, session: requests.Session) -> Path:
        filename = self.output_dir / f"Tariff_{tid}.xml"
        if filename.exists():
            self.logger.info("Skipping %s (already downloaded)", filename.name)
            return filename

        url = EXPORT_URL.format(tid=tid)
        response = session.get(url, timeout=self.request_timeout)
        response.raise_for_status()
        soup = self._to_soup(response.text)

        data = self._extract_inputs(soup)
        for field in STATUSES:
            data[field] = "on"
        data[PLAIN_TEXT_FIELD] = "on"
        data["__EVENTTARGET"] = EVENT_TARGET_EXPORT
        data["__EVENTARGUMENT"] = ""

        time.sleep(self.export_sleep)
        export_response = session.post(url, data=data, timeout=self.request_timeout * 2)
        export_response.raise_for_status()

        with open(filename, "wb") as handle:
            handle.write(export_response.content)
        self.logger.info("Downloaded %s", filename.name)
        return filename

    def run(self) -> None:
        try:
            self.logger.info("Starting tariff id collection")
            tids = sorted(self.collect_tariff_ids(), key=int)
            self.logger.info("Found %d tariff ids", len(tids))
            self.logger.info("Saving XML files to %s", self.output_dir)

            if self.max_files:
                tids = tids[: self.max_files]
                self.logger.info("Limiting to first %d ids", len(tids))

            session = self._session()

            for index, tid in enumerate(tids, start=1):
                for attempt in range(1, self.retry_attempts + 1):
                    try:
                        self.logger.info("[%d/%d] Fetching tariff %s", index, len(tids), tid)
                        self.download_tariff_xml(tid, session)
                        break
                    except Exception as exc:  # pragma: no cover - network errors
                        self.logger.warning(
                            "Attempt %d failed for tid %s: %s", attempt, tid, exc
                        )
                        if attempt == self.retry_attempts:
                            self.logger.error("Giving up on tid %s", tid)
                        else:
                            time.sleep(self.export_sleep)
        except Exception as exc:
            self.logger.error("Fatal error during download process: %s", exc)


def main() -> None:
    downloader = FERCTariffDownloader()
    downloader.run()


if __name__ == "__main__":
    main()
