# vigilant-octo-spoon

## FERC Tariff XML Downloader

This repository contains an automated tool to download XML files from the FERC (Federal Energy Regulatory Commission) tariff website at https://etariff.ferc.gov/TariffList.aspx.

### Overview

The tool drives the DevExpress grid with Selenium to gather tariff ids, then
uses HTTP requests to download the XML exports:
- Navigates to the "All Tariffs" view and steps through each page of the grid
- Extracts every tariff export id exposed in the pagination sequence
- Posts the same payload a browser would send to download the XML export with
  all status filters enabled and the plain text format selected
- Saves the XML files to the `TariffXML` folder

### Requirements

- Python 3.7+
- Google Chrome installed (required for Selenium WebDriver)
- Internet connection

### Installation

1. Clone this repository:
```bash
git clone https://github.com/HyprPixl/vigilant-octo-spoon.git
cd vigilant-octo-spoon
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

### Usage

Run the downloader:
```bash
python run_downloader.py
```

Or run the main script directly:
```bash
python ferc_tariff_downloader.py
```

### Features

- **Hybrid workflow**: Uses Selenium solely for pagination and requests for downloads
- **Error handling**: Continues processing even if individual downloads fail
- **Logging**: Comprehensive logging to both console and file (`ferc_downloader.log`)
- **Progress tracking**: Shows current page and download progress
- **Configurable download folder**: Downloads to `TariffXML` folder by default

### Output

- Downloaded XML files are saved to the `TariffXML` folder
- Log file `ferc_downloader.log` contains detailed execution logs
- Console output shows real-time progress

### Safety Features

- Page limit safety check to prevent infinite loops
- Graceful error handling for network issues
- Retry loop for individual downloads

### Troubleshooting

If you encounter issues:
1. Check the log file `ferc_downloader.log` for detailed error information
2. Check your internet connection
3. The website structure may have changed - inspect the request workflow in `ferc_tariff_downloader.py`
