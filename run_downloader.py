#!/usr/bin/env python3
"""
Simple runner script for FERC Tariff XML Downloader
"""

import sys
import os

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ferc_tariff_downloader import FERCTariffDownloader

if __name__ == "__main__":
    print("FERC Tariff XML Downloader")
    print("=" * 40)
    print("This script will download XML files from https://etariff.ferc.gov/TariffList.aspx")
    print("Files will be saved to the 'TariffXML' folder")
    print("Press Ctrl+C to stop the process at any time")
    print()
    
    try:
        downloader = FERCTariffDownloader()
        downloader.run()
    except KeyboardInterrupt:
        print("\nDownload process interrupted by user")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)