#!/usr/bin/env python3
"""
Test script for FERC Tariff XML Downloader
This validates the setup without running the full automation.
"""

import os
import sys
import tempfile
import shutil

def test_imports():
    """Test that all required modules can be imported."""
    try:
        import requests
        from bs4 import BeautifulSoup  # noqa: F401  (import check only)
        import selenium  # noqa: F401
        import webdriver_manager  # noqa: F401
        from ferc_tariff_downloader import FERCTariffDownloader
        print("✓ All imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False

def test_downloader_init():
    """Test that the downloader can be initialized."""
    try:
        from ferc_tariff_downloader import FERCTariffDownloader
        
        # Create a temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            test_folder = os.path.join(temp_dir, "TestXML")
            downloader = FERCTariffDownloader(download_folder=test_folder)

            # Check that folder was created
            if os.path.exists(downloader.output_dir):
                print("✓ Downloader initialization successful")
                print(f"  - Download folder created: {downloader.output_dir}")
                return True
            else:
                print("✗ Download folder not created")
                return False
    except Exception as e:
        print(f"✗ Downloader initialization failed: {e}")
        return False

def test_config():
    """Test that configuration can be loaded."""
    try:
        import config
        print("✓ Configuration loaded successfully")
        print(f"  - Base URL: {config.base_url}")
        print(f"  - Default folder: {config.download_folder}")
        print(f"  - Max pages: {config.max_pages}")
        return True
    except Exception as e:
        print(f"✗ Configuration error: {e}")
        return False

def main():
    """Run all tests."""
    print("FERC Tariff Downloader - Test Suite")
    print("=" * 40)
    
    tests = [
        ("Testing imports", test_imports),
        ("Testing downloader initialization", test_downloader_init),
        ("Testing configuration", test_config)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{test_name}...")
        if test_func():
            passed += 1
    
    print(f"\nTest Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✓ All tests passed! The downloader is ready to use.")
        print("\nTo run the actual downloader:")
        print("  python run_downloader.py")
        print("  or")
        print("  python ferc_tariff_downloader.py")
    else:
        print("✗ Some tests failed. Please check the error messages above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
