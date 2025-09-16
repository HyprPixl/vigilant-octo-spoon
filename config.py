# FERC Tariff Downloader Configuration

# Download settings
download_folder = "TariffXML"
base_url = "https://etariff.ferc.gov/TariffList.aspx"

# Browser settings
headless = False  # Set to True to run browser in background
window_width = 1920
window_height = 1080

# Timing settings (in seconds)
page_load_wait = 3
popup_wait = 10
download_wait = 3
checkbox_delay = 0.1

# Safety settings
max_pages = 350  # Safety limit to prevent infinite loops
retry_attempts = 3

# Logging settings
log_level = "INFO"  # DEBUG, INFO, WARNING, ERROR
log_to_file = True
log_filename = "ferc_downloader.log"