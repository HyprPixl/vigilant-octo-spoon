# vigilant-octo-spoon

## FERC Tariff XML Downloader

This repository contains an automated tool to download XML files from the FERC (Federal Energy Regulatory Commission) tariff website at https://etariff.ferc.gov/TariffList.aspx.

### Overview

The tool uses Selenium WebDriver to:
- Navigate through all 300+ pages of tariff documents
- Click on XML links in the XML column
- Handle the Export XML popup by:
  - Selecting all status checkboxes
  - Choosing plain text XML format
  - Clicking export to download files
- Save all XML files to a `TariffXML` folder

### Requirements

- Python 3.7+
- Chrome browser installed
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

- **Automatic driver management**: Uses webdriver-manager to handle Chrome driver installation
- **Robust element detection**: Multiple fallback selectors for finding page elements
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
- Proper browser cleanup on exit

### Troubleshooting

If you encounter issues:
1. Check the log file `ferc_downloader.log` for detailed error information
2. Ensure Chrome browser is installed and up to date
3. Check your internet connection
4. The website structure may have changed - review the selectors in the code