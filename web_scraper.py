from playwright.sync_api import sync_playwright, TimeoutError
import asyncio
from pathlib import Path
from datetime import datetime
from config import CompanyConfig, WebsiteCredentials
import time
import os
import json
import random
import re

class WebScraper:
    def __init__(self, company_config: CompanyConfig, headless: bool = False, manual_mode: bool = False, pure_manual: bool = False, persistent_browser: bool = False, incognito_mode: bool = False):
        self.config = company_config
        self.output_dir = Path(company_config.output_directory)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # Reduce default timeout to 30 seconds
        self.timeout = 30000
        # Manual intervention timeout (60 seconds instead of 120)
        self.manual_timeout = 60000
        self.headless = headless
        self.manual_mode = manual_mode
        self.pure_manual = pure_manual
        self.persistent_browser = persistent_browser
        self.incognito_mode = incognito_mode
        
        # Create a sessions directory
        self.sessions_dir = Path("./sessions")
        self.sessions_dir.mkdir(exist_ok=True)
        
        # Create browser data directory for persistent profiles
        self.browser_data_dir = Path("./browser_data")
        self.browser_data_dir.mkdir(exist_ok=True)
        
        # Session files for each retailer
        self.walmart_session_file = self.sessions_dir / f"{self.config.name}_walmart_session.json"
        self.amazon_session_file = self.sessions_dir / f"{self.config.name}_amazon_session.json"
        
        # Browser profile directories for each retailer
        self.walmart_profile_dir = self.browser_data_dir / f"{self.config.name}_walmart"
        self.amazon_profile_dir = self.browser_data_dir / f"{self.config.name}_amazon"

    def _setup_browser(self, playwright, session_file: Path = None, profile_dir: Path = None):
        """Set up a browser instance with appropriate configuration."""
        # Configure browser options
        browser_args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-features=IsolateOrigins,site-per-process',
            '--disable-site-isolation-trials',
            '--disable-web-security',
            '--disable-features=BlockInsecurePrivateNetworkRequests',
            '--disable-popup-blocking',
            '--disable-extensions',
            '--disable-component-extensions-with-background-pages',
            '--disable-default-apps',
            '--mute-audio',
            '--no-default-browser-check',
            '--no-first-run',
            '--no-service-autorun',
            '--password-store=basic',
            '--use-mock-keychain',
            '--enable-features=NetworkServiceInProcess2',
            '--disable-hang-monitor',
            '--disable-ipc-flooding-protection',
            '--disable-renderer-backgrounding',
            '--metrics-recording-only',
            '--no-sandbox',
            '--window-size=1920,1080',
            '--enable-javascript',
            '--plugins-enabled=true',
            '--plugin.state=enabled',
            '--enable-plugins',
            '--enable-pdf-viewer',  # Ensure PDF viewer is enabled
            '--pdf-viewer-enabled=true',  # Explicitly enable PDF viewer
            '--print-to-pdf-no-header',  # Remove headers when printing to PDF
            '--enable-print-browser',  # Enable browser printing capabilities
            '--enable-print-preview',  # Enable print preview
        ]
        
        try:
            if self.persistent_browser and profile_dir:
                # Create profile directory if it doesn't exist
                profile_dir.mkdir(parents=True, exist_ok=True)
                print(f"Using persistent browser profile at: {profile_dir}")
                
                # Delete any incognito preferences in the profile
                try:
                    prefs_path = profile_dir / "Default" / "Preferences"
                    if prefs_path.exists():
                        print("Checking browser preferences file...")
                        with open(prefs_path, 'r') as f:
                            prefs = json.load(f)
                        
                        # Remove incognito mode settings if present
                        if 'profile' in prefs:
                            if 'last_active_profiles' in prefs['profile']:
                                prefs['profile'].pop('last_active_profiles', None)
                            if 'incognito' in prefs['profile']:
                                prefs['profile'].pop('incognito', None)
                            if 'guest_profile' in prefs['profile']:
                                prefs['profile'].pop('guest_profile', None)
                        
                        # Write back the modified preferences
                        with open(prefs_path, 'w') as f:
                            json.dump(prefs, f)
                        print("Updated browser preferences to disable incognito mode")
                except Exception as e:
                    print(f"Error updating browser preferences: {e}")
                
                # Launch with Chromium (more reliable)
                print("Launching Chromium browser with persistent profile...")
                browser = playwright.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    headless=self.headless,
                    args=browser_args,
                    viewport={"width": 1920, "height": 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
                    locale='en-US',
                    timezone_id='America/New_York',
                    accept_downloads=True,
                    ignore_https_errors=True,
                    has_touch=True,
                    color_scheme='light',
                    reduced_motion='no-preference',
                    extra_http_headers={
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Upgrade-Insecure-Requests': '1',
                        'Sec-Fetch-Dest': 'document',
                        'Sec-Fetch-Mode': 'navigate',
                        'Sec-Fetch-Site': 'none',
                        'Sec-Fetch-User': '?1',
                        'Sec-CH-UA': '"Chromium";v="120", "Not-A.Brand";v="99"',
                        'Sec-CH-UA-Mobile': '?0',
                        'Sec-CH-UA-Platform': '"Windows"'
                    }
                )
                print("Successfully launched browser with persistent profile")
                
                # In persistent mode, browser is also the context
                context = browser
                browser_obj = None
            else:
                # Launch regular browser
                print("Launching Chromium browser...")
                browser_obj = playwright.chromium.launch(
                    headless=self.headless,
                    args=browser_args if not self.incognito_mode else []
                )
                print("Successfully launched browser")
                
                # Create a context
                context = browser_obj.new_context(
                    # Use a larger viewport with proper aspect ratio
                    viewport={"width": 1920, "height": 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
                    locale='en-US',
                    timezone_id='America/New_York',
                    accept_downloads=True,
                    ignore_https_errors=True,
                    has_touch=True,
                    color_scheme='light',
                    reduced_motion='no-preference',
                    extra_http_headers={
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Upgrade-Insecure-Requests': '1',
                        'Sec-Fetch-Dest': 'document',
                        'Sec-Fetch-Mode': 'navigate',
                        'Sec-Fetch-Site': 'none',
                        'Sec-Fetch-User': '?1',
                        'Sec-CH-UA': '"Chromium";v="120", "Not-A.Brand";v="99"',
                        'Sec-CH-UA-Mobile': '?0',
                        'Sec-CH-UA-Platform': '"Windows"'
                    }
                )
            
            # Load session if available
            if session_file and session_file.exists() and not self.persistent_browser:
                print(f"Loading saved session from {session_file}...")
                try:
                    cookies = json.loads(session_file.read_text())
                    context.add_cookies(cookies)
                    print("Session loaded successfully")
                except Exception as e:
                    print(f"Error loading session: {e}")
            
            # Set default timeout
            context.set_default_timeout(self.timeout)
            
            # Add script to enable scrollbars
            context.add_init_script("""
                window.addEventListener('DOMContentLoaded', () => {
                    const style = document.createElement('style');
                    style.textContent = `
                        ::-webkit-scrollbar {
                            width: 12px;
                            height: 12px;
                        }
                        ::-webkit-scrollbar-track {
                            background: #f1f1f1;
                        }
                        ::-webkit-scrollbar-thumb {
                            background: #888;
                            border-radius: 6px;
                        }
                        ::-webkit-scrollbar-thumb:hover {
                            background: #555;
                        }
                        html, body {
                            overflow: auto !important;
                            max-width: none !important;
                        }
                    `;
                    document.head.appendChild(style);
                });
            """)
            
            return browser_obj, context
        except Exception as e:
            print(f"Error setting up browser: {e}")
            # Try one more time with basic settings
            print("Trying again with basic browser settings...")
            browser_obj = playwright.chromium.launch(
                headless=self.headless
            )
            context = browser_obj.new_context(
                viewport={"width": 1920, "height": 1080},
                accept_downloads=True
            )
            return browser_obj, context

    def _wait_for_page_load(self, page):
        """Wait for the page to be fully loaded."""
        try:
            # Wait for the page to be fully loaded
            page.wait_for_load_state("domcontentloaded", timeout=self.timeout)
            page.wait_for_load_state("networkidle", timeout=self.timeout)
            
            # Additional wait to ensure JavaScript has executed
            page.wait_for_timeout(2000)
            
            print("Page fully loaded")
            return True
        except Exception as e:
            print(f"Error waiting for page to load: {e}")
            return False

    def _save_session(self, context, session_file):
        """Save the current browser session to a file"""
        try:
            # Create the sessions directory if it doesn't exist
            session_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Get the current storage state (cookies and localStorage)
            storage_state = {
                'cookies': context.cookies(),
                'origins': []  # We'll only use cookies for now
            }
            
            # Save to file
            with open(session_file, 'w') as f:
                json.dump(storage_state, f)
            
            print(f"Session saved to {session_file}")
        except Exception as e:
            print(f"Error saving session: {e}")

    def _handle_download(self, download, target_dir, prefix=""):
        """Handle a download event from Playwright."""
        try:
            # Ensure the target directory exists
            target_dir = Path(target_dir)
            target_dir.mkdir(exist_ok=True)
            
            # Get the suggested filename from the download
            suggested_name = download.suggested_filename
            print(f"Download started with suggested filename: {suggested_name}")
            
            # Create a unique filename with the provided prefix
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{prefix}{timestamp}_{suggested_name}"
            if not filename:
                # If no filename is suggested, create a generic one
                extension = ".pdf"  # Default to PDF for invoices
                filename = f"{prefix}{timestamp}{extension}"
            
            # Full path for the download
            download_path = target_dir / filename
            
            # Save the download
            download.save_as(str(download_path))
            print(f"Download saved to: {download_path}")
            
            return download_path
        except Exception as e:
            print(f"Error handling download: {e}")
            return None
    
    def _verify_pdf_download(self, pdf_path):
        """Verify that the downloaded PDF file is valid and not empty."""
        try:
            # Check if the file exists
            pdf_path = Path(pdf_path)
            if not pdf_path.exists():
                print(f"PDF file does not exist: {pdf_path}")
                return False
            
            # Check if the file has content
            file_size = pdf_path.stat().st_size
            if file_size == 0:
                print(f"PDF file is empty: {pdf_path}")
                return False
            
            print(f"PDF file verified: {pdf_path} (size: {file_size} bytes)")
            
            # For more thorough verification, we could use PyPDF2 to check if it's a valid PDF
            try:
                import PyPDF2
                with open(pdf_path, 'rb') as f:
                    pdf_reader = PyPDF2.PdfReader(f)
                    num_pages = len(pdf_reader.pages)
                    print(f"PDF has {num_pages} pages")
                    if num_pages == 0:
                        print("PDF has no pages")
                        return False
            except ImportError:
                print("PyPDF2 not installed, skipping detailed PDF verification")
            except Exception as pdf_error:
                print(f"Error verifying PDF content: {pdf_error}")
                return False
            
            return True
        except Exception as e:
            print(f"Error verifying PDF download: {e}")
            return False

    def _extract_purchase_date(self, page):
        """Extract the purchase date from the invoice page."""
        try:
            # Try multiple selectors to find the purchase date element
            date_selectors = [
                "h1.print-bill-date", 
                "h1.w_kV33.w_LD4J.w_mvVb.f3.f-subheadline-m.di-m.dark-gray-m.print-bill-date",
                "h1:has-text('purchase')",
                "div:has-text('Order placed')",
                "div:has-text('Purchase date')",
                "span:has-text('Order placed')",
                "span:has-text('Purchase date')"
            ]
            
            for selector in date_selectors:
                date_element = page.query_selector(selector)
                if date_element:
                    date_text = date_element.text_content()
                    print(f"Found potential purchase date text: {date_text}")
                    
                    # Try different regex patterns to extract the date
                    date_patterns = [
                        r'([A-Za-z]+\s+\d+,\s+\d{4})',  # "Jul 29, 2024"
                        r'(\d{1,2}/\d{1,2}/\d{2,4})',   # "7/29/2024" or "7/29/24"
                        r'Order placed\s+([A-Za-z]+\s+\d+,\s+\d{4})',  # "Order placed Jul 29, 2024"
                        r'Purchase date\s+([A-Za-z]+\s+\d+,\s+\d{4})'  # "Purchase date Jul 29, 2024"
                    ]
                    
                    for pattern in date_patterns:
                        date_match = re.search(pattern, date_text)
                        if date_match:
                            date_str = date_match.group(1)
                            try:
                                # Try different date formats
                                for date_format in ["%b %d, %Y", "%m/%d/%Y", "%m/%d/%y"]:
                                    try:
                                        purchase_date = datetime.strptime(date_str, date_format)
                                        print(f"Extracted purchase date: {purchase_date}")
                                        return purchase_date
                                    except ValueError:
                                        continue
                            except Exception as e:
                                print(f"Error parsing date '{date_str}': {e}")
            
            # If we couldn't find the date with selectors, try to extract it from the page URL
            current_url = page.url
            url_date_match = re.search(r'purchaseDate=(\d{4}-\d{2}-\d{2})', current_url)
            if url_date_match:
                date_str = url_date_match.group(1)
                try:
                    purchase_date = datetime.strptime(date_str, "%Y-%m-%d")
                    print(f"Extracted purchase date from URL: {purchase_date}")
                    return purchase_date
                except Exception as e:
                    print(f"Error parsing date from URL '{date_str}': {e}")
            
            # If all attempts fail, take a screenshot for debugging
            screenshot_path = self.output_dir / "purchase_date_extraction_failed.png"
            page.screenshot(path=str(screenshot_path))
            print(f"Could not find purchase date, saved screenshot to {screenshot_path}")
            
            # If we can't find the date, return None
            return None
        except Exception as e:
            print(f"Error extracting purchase date: {e}")
            return None
    
    def _get_invoice_directory(self, company, purchase_date=None):
        """Get the directory for saving invoices based on purchase date."""
        # Base downloads directory
        downloads_dir = Path("downloads") / company
        
        if purchase_date:
            # Organize by year/month
            year_dir = downloads_dir / str(purchase_date.year)
            month_dir = year_dir / purchase_date.strftime("%m-%b")  # e.g., "07-Jul"
            
            # Create directories if they don't exist
            month_dir.mkdir(parents=True, exist_ok=True)
            print(f"Created/verified directory structure: {month_dir}")
            return month_dir
        else:
            # Fallback to current date if purchase date not available
            current_date = datetime.now()
            year_dir = downloads_dir / str(current_date.year)
            month_dir = year_dir / current_date.strftime("%m-%b")
            
            # Create a special "unknown_date" subfolder to distinguish these invoices
            unknown_date_dir = month_dir / "unknown_date"
            unknown_date_dir.mkdir(parents=True, exist_ok=True)
            print(f"Could not determine purchase date, using fallback directory: {unknown_date_dir}")
            return unknown_date_dir
    
    def _check_invoice_exists(self, directory, order_number):
        """Check if an invoice for this order already exists."""
        if not order_number or order_number == "unknown":
            print("Cannot check for existing invoice: order number is unknown")
            return False
            
        # Look for any file with this order number in the filename
        pattern = f"*{order_number}*"
        existing_files = list(directory.glob(pattern))
        
        if existing_files:
            print(f"Invoice for order {order_number} already exists: {existing_files[0]}")
            return True
        return False

    def scrape_walmart(self):
        if not self.config.walmart_credentials:
            print(f"No Walmart credentials for {self.config.name}")
            return

        with sync_playwright() as playwright:
            browser, context = self._setup_browser(
                playwright, 
                self.walmart_session_file,
                self.walmart_profile_dir if self.persistent_browser else None
            )
            page = context.new_page()
            
            try:
                # Always start with the homepage for a more natural browsing experience
                print("Loading Walmart homepage...")
                try:
                    page.goto('https://www.walmart.com', timeout=60000)  # 60 second timeout for initial load
                    print("Walmart homepage loaded successfully")
                except Exception as e:
                    print(f"Error loading Walmart homepage: {e}")
                    screenshot_path = self.output_dir / "walmart_homepage_error.png"
                    page.screenshot(path=str(screenshot_path))
                    print(f"Saved homepage error screenshot to {screenshot_path}")
                
                # Check if we're already logged in
                print("Checking login status...")
                try:
                    # Try to navigate to the account page to check login status
                    page.goto('https://www.walmart.com/account', timeout=30000)
                    
                    # Wait a moment for the page to load
                    page.wait_for_timeout(5000)
                    
                    # Check if we're logged in by looking for account elements
                    logged_in = False
                    try:
                        # Look for elements that indicate we're logged in
                        account_selectors = [
                            'text="Account Home"',
                            'text="Account"',
                            'text="Sign Out"',
                            '[data-testid="account-username"]'
                        ]
                        
                        for selector in account_selectors:
                            if page.is_visible(selector, timeout=5000):
                                logged_in = True
                                print(f"Found logged-in indicator: {selector}")
                                break
                    except:
                        pass
                    
                    if logged_in:
                        print("Already logged into Walmart (session restored)")
                    else:
                        print("Not logged in, proceeding to login process")
                except Exception as e:
                    print(f"Error checking login status: {e}")
                    # Continue with login process
                
                # If we're not logged in, proceed with login
                if not logged_in:
                    # Try automated login
                    try:
                        # Navigate to login page if not already there
                        if "account/login" not in page.url:
                            print("Navigating to login page...")
                            page.goto('https://www.walmart.com/account/login', timeout=30000)
                        
                        # Wait for the login form
                        print("Looking for login form...")
                        login_form_visible = False
                        try:
                            login_form_visible = page.wait_for_selector('#email-input', timeout=10000, state='visible') is not None
                        except:
                            print("Login form not immediately visible")
                        
                        if login_form_visible:
                            print("Login form found, filling credentials...")
                            # Type email with random delays
                            print("Typing email address...")
                            page.fill('#email-input', '')  # Clear the field first
                            for char in self.config.walmart_credentials.username:
                                page.type('#email-input', char, delay=random.uniform(50, 150))
                                page.wait_for_timeout(random.randint(10, 50))
                            
                            # Small delay between fields
                            page.wait_for_timeout(random.randint(500, 1500))
                            
                            # Type password with random delays
                            print("Typing password...")
                            page.fill('#password-input', '')  # Clear the field first
                            for char in self.config.walmart_credentials.password:
                                page.type('#password-input', char, delay=random.uniform(50, 150))
                                page.wait_for_timeout(random.randint(10, 50))
                            
                            # Small delay before clicking sign-in
                            page.wait_for_timeout(random.randint(500, 1500))
                            
                            print("Clicking sign-in button...")
                            page.click('#sign-in-form-submit-btn')
                            
                            # Wait for navigation or verification
                            print("Waiting for login response...")
                            page.wait_for_timeout(5000)
                        else:
                            print("Login form not found")
                            # Take a screenshot for debugging
                            screenshot_path = self.output_dir / "walmart_login_form_missing.png"
                            page.screenshot(path=str(screenshot_path))
                            print(f"Saved screenshot to {screenshot_path}")
                    except Exception as e:
                        print(f"Error during automated login: {e}")
                        screenshot_path = self.output_dir / "walmart_login_error.png"
                        page.screenshot(path=str(screenshot_path))
                        print(f"Saved login error screenshot to {screenshot_path}")
                    
                    # Wait a bit longer for login to complete
                    print("Waiting for login process to complete...")
                    page.wait_for_timeout(10000)
                    
                    # Check if login was successful
                    logged_in = self.check_walmart_login(page)
                    if logged_in:
                        print("Login successful")
                    else:
                        print("Login may have failed, but continuing anyway")
                        # Take a screenshot for debugging
                        screenshot_path = self.output_dir / "walmart_login_check_failed.png"
                        page.screenshot(path=str(screenshot_path))
                        print(f"Saved login check screenshot to {screenshot_path}")
                
                # After login, navigate to Purchase Orders page
                print("Navigating to Purchase Orders page...")
                
                try:
                    # First check if we're already on the orders page
                    current_url = page.url
                    print(f"Current URL after login: {current_url}")
                    
                    # If already on orders page, no need to navigate
                    if '/orders' in current_url:
                        print("Already on the orders page, no navigation needed")
                        found_link = True
                    
                    # Variable to track navigation success
                    found_link = False
                    
                    # Check if we're already on the orders page after potential navigation
                    current_url = page.url
                    if '/orders' in current_url:
                        print("Successfully reached orders page")
                        found_link = True
                    
                    # If we still couldn't navigate to the orders page, try one more direct approach
                    if not found_link:
                        print("Trying direct navigation to the orders page...")
                        try:
                            page.goto('https://www.walmart.com/orders', timeout=30000)
                            page.wait_for_load_state('domcontentloaded', timeout=15000)
                            
                            current_url = page.url
                            if '/orders' in current_url:
                                print("Successfully navigated to orders page")
                                found_link = True
                            else:
                                print(f"Navigation attempt failed. Current URL: {current_url}")
                                # Log error but continue with the process
                        except Exception as e:
                            print(f"Error during final navigation attempt: {e}")
                    
                except Exception as e:
                    print(f"Error navigating to Purchase Orders page: {e}")
                    screenshot_path = self.output_dir / "walmart_navigation_error.png"
                    page.screenshot(path=str(screenshot_path))
                    print(f"Saved navigation error screenshot to {screenshot_path}")
                    print("Continuing with the current page despite navigation error")
                
                # Create date-based directory for downloads
                date_dir = self.output_dir / datetime.now().strftime("%Y-%m")
                date_dir.mkdir(exist_ok=True)
                print(f"Saving invoices to: {date_dir}")

                # Setup download handler with a dynamic prefix
                self.current_order_number = "unknown"
                
                def download_handler(download):
                    prefix = f"walmart_invoice_{self.current_order_number}_"
                    return self._handle_download(download, date_dir, prefix)
                
                # Set the download handler
                page.on('download', download_handler)
                
                # Wait for the orders page to load completely
                print("Waiting for orders page to load...")
                try:
                    page.wait_for_load_state('domcontentloaded', timeout=20000)
                    page.wait_for_load_state('load', timeout=20000)
                except Exception as e:
                    print(f"Error waiting for orders page: {e}")
                    # Take a screenshot for debugging
                    screenshot_path = self.output_dir / "walmart_orders_timeout.png"
                    page.screenshot(path=str(screenshot_path))
                    print(f"Saved timeout screenshot to {screenshot_path}")
                
                # Initialize pagination variables
                current_page = 1
                has_more_pages = True
                processed_orders = 0
                total_orders_processed = 0
                
                # Process all pages of orders
                while has_more_pages:
                    print(f"\n--- Processing orders page {current_page} ---\n")
                    
                    # Take a screenshot of the current page for debugging
                    page_screenshot_path = self.output_dir / f"walmart_orders_page_{current_page}.png"
                    page.screenshot(path=str(page_screenshot_path))
                    print(f"Saved page {current_page} screenshot to {page_screenshot_path}")
                
                    # Find all "View order details" buttons with increased timeout and debugging
                    print("Looking for 'View order details' buttons...")
                    view_details_buttons = []
                    
                    # Try multiple selectors with explicit timeout and error handling
                    view_details_selectors = [
                        '[data-automation-id*="view-order-details-*"]',
                        '[data-automation-id*="order-details"]',
                        '[data-testid*="order-details"]',
                        'a[href*="order-details"]',
                        'a[href*="order/details"]'
                    ]
                    
                    for selector in view_details_selectors:
                        try:
                            print(f"Trying selector: {selector}")
                            buttons = page.query_selector_all(selector)
                            if buttons:
                                print(f"Found {len(buttons)} buttons using selector: {selector}")
                                view_details_buttons = buttons
                                break
                        except Exception as e:
                            print(f"Error with selector '{selector}': {e}")
                    
                    if not view_details_buttons:
                        print("No order details buttons found. Taking a screenshot for debugging...")
                        screenshot_path = self.output_dir / f"walmart_no_orders_found_page_{current_page}.png"
                        page.screenshot(path=str(screenshot_path))
                        print(f"Saved screenshot to {screenshot_path}")
                        
                        # Check the HTML content for debugging
                        print("Checking page content for debugging...")
                        page_content = page.content()
                        if "order details" in page_content.lower() or "view order" in page_content.lower():
                            print("Page content contains 'order details' or 'view order' text, but selectors failed to match")
                        else:
                            print("Page content does not contain expected order-related text")
                        
                        # If no orders found on first page, try to navigate to next page
                        if current_page == 1:
                            print("No orders found on first page, will try to navigate to next page")
                        else:
                            print("No orders found on current page, pagination complete")
                            has_more_pages = False
                    else:
                        print(f"Found {len(view_details_buttons)} 'View order details' buttons")
                        
                        # Process each order
                        order_links = page.query_selector_all('a:has-text("View details"), a:has-text("Order details"), [data-automation-id*="order-detail"]')
                        print(f"Found {len(order_links)} order links")
                        
                        if len(order_links) == 0:
                            print("No order links found, trying alternative selectors...")
                            alternative_selectors = [
                                'a:has-text("View order")',
                                'button:has-text("View order")',
                                '[data-testid*="order-card"] a',
                                '[data-automation-id*="order-card"] a'
                            ]
                            
                            for selector in alternative_selectors:
                                try:
                                    links = page.query_selector_all(selector)
                                    if links and len(links) > 0:
                                        print(f"Found {len(links)} order links with selector: {selector}")
                                        order_links = links
                                        break
                                except Exception as e:
                                    print(f"Error with selector {selector}: {e}")
                        
                        # Process each order on this page
                        i = 0
                        page_orders_processed = 0
                        while i < len(order_links):
                            try:
                                print(f"Processing order {i+1}/{len(order_links)} on page {current_page}")
                                
                                # Create a directory for this date if it doesn't exist
                                date_str = datetime.now().strftime('%Y-%m-%d')
                                date_dir = self.output_dir / date_str
                                date_dir.mkdir(exist_ok=True)
                                
                                # Store the current URL before clicking
                                orders_page_url = page.url
                                
                                # Get the order link
                                order_link = order_links[i]
                                
                                # Try to extract order number before clicking
                                order_number = "unknown"
                                try:
                                    # Try to extract order number from data-automation-id attribute
                                    data_automation_id = order_link.get_attribute('data-automation-id')
                                    if data_automation_id and "view-order-details-link-" in data_automation_id:
                                        order_number = data_automation_id.split("view-order-details-link-")[1]
                                        print(f"Extracted order number: {order_number}")
                                    else:
                                        # Try to extract from aria-label
                                        aria_label = order_link.get_attribute('aria-label')
                                        if aria_label and "order number" in aria_label:
                                            # Format: "View details for order number XXXXXXXXXX"
                                            order_number = aria_label.split("order number")[1].strip()
                                            print(f"Extracted order number from aria-label: {order_number}")
                                except Exception as e:
                                    print(f"Could not extract order number: {e}")
                                
                                print(f"Processing order {i+1}/{len(order_links)} (Order #{order_number})...")
                                
                                # Update the current order number for the download handler
                                self.current_order_number = order_number
                                
                                # Click the order link to view details
                                print(f"Clicking on order link {i+1}...")
                                try:
                                    order_link.click()
                                    print("Order link clicked, waiting for details page to load...")
                                    
                                    # Wait for navigation to complete
                                    try:
                                        # Wait for the page to be fully loaded
                                        page.wait_for_load_state("domcontentloaded", timeout=self.timeout)
                                        
                                        # Additional wait to ensure JavaScript has executed
                                        page.wait_for_timeout(2000)
                                        
                                        print("Page fully loaded")
                                    except Exception as e:
                                        print(f"Error waiting for page to load: {e}")
                                    
                                    # Try to get the order number from the details page
                                    try:
                                        # Look for elements containing the order number
                                        order_number_elements = page.query_selector_all('div.f-subheadline.m:has-text("Order#")')
                                        for elem in order_number_elements:
                                            text = elem.text_content()
                                            match = re.search(r'Order\s+#?\s*(\w+)', text)
                                            if match:
                                                order_number = match.group(1)
                                                print(f"Found order number: {order_number}")
                                                break
                                    except Exception as e:
                                        print(f"Error getting order number: {e}")
                                    
                                    # Extract purchase date
                                    purchase_date = self._extract_purchase_date(page)
                                    if purchase_date:
                                        # Create directory based on purchase date
                                        invoice_dir = self._get_invoice_directory(self.config.name, purchase_date)
                                        print(f"Saving invoice to directory: {invoice_dir}")
                                        
                                        # Check if invoice already exists
                                        if self._check_invoice_exists(invoice_dir, order_number):
                                            print("Skipping this order as the invoice already exists")
                                            i += 1
                                            page_orders_processed += 1
                                            continue
                                    else:
                                        print("Could not extract purchase date, using default directory")
                                        invoice_dir = self._get_invoice_directory(self.config.name)
                                        print(f"Saving invoice to directory: {invoice_dir}")
                                    
                                    # Process the invoice download using our existing code
                                    downloaded_invoices = 0
                                        
                                    # Third attempt: If no invoices were downloaded, try using page.pdf() as a fallback
                                    if downloaded_invoices == 0:
                                        print("Downloading using page.pdf()")
                                        pdf_path = invoice_dir / f"walmart_invoice_{order_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                                        
                                        try:
                                            # Try to scroll through the page to ensure all content is loaded
                                            page.evaluate("""() => {
                                                window.scrollTo(0, 0);
                                                let totalHeight = 0;
                                                let distance = 100;
                                                let timer = setInterval(() => {
                                                    let scrollHeight = document.body.scrollHeight;
                                                    window.scrollBy(0, distance);
                                                    totalHeight += distance;
                                                    if(totalHeight >= scrollHeight){
                                                        clearInterval(timer);
                                                    }
                                                }, 100);
                                            }""")
                                            page.wait_for_timeout(3000)  # Wait for scrolling to complete
                                            
                                            # Configure PDF options for better rendering
                                            pdf_data = page.pdf(
                                                format="Letter",
                                                print_background=True,
                                                margin={"top": "0.5in", "right": "0.5in", "bottom": "0.5in", "left": "0.5in"},
                                                scale=0.9  # Slightly scale down to ensure everything fits
                                            )
                                            
                                            with open(pdf_path, 'wb') as f:
                                                f.write(pdf_data)
                                            print(f"Successfully saved PDF to {pdf_path}")
                                            
                                            # Verify the PDF
                                            self._verify_pdf_download(pdf_path)
                                        except Exception as e:
                                            print(f"Error saving PDF: {e}")
                                            screenshot_path = self.output_dir / f"walmart_order_{order_number}_error.png"
                                            page.screenshot(path=str(screenshot_path))
                                            print(f"Saved error screenshot to {screenshot_path}")
                                    
                                    # Go back to the orders page
                                    print("Navigating back to orders page...")
                                    try:
                                        # Use the browser's back button to return to the orders page
                                        print("Using browser back button to return to orders page")
                                        page.go_back()
                                        
                                        # Enhanced waiting for page to fully load
                                        print("Waiting for orders page to fully load after navigation...")
                                        page.wait_for_load_state('domcontentloaded', timeout=15000)
                                        
                                        # Wait for the page to be fully loaded
                                        try:
                                            print("Waiting for network activity to settle...")
                                            page.wait_for_load_state('networkidle', timeout=15000)
                                        except Exception as e:
                                            print(f"Network idle timeout (not critical): {e}")
                                            
                                        # Additional wait to ensure JavaScript has executed
                                        print("Additional wait to ensure all elements are rendered...")
                                        page.wait_for_timeout(7000)  # Increased from 3000 to 7000 ms
                                        
                                        # Take a screenshot after navigation
                                        back_screenshot_path = self.output_dir / f"walmart_back_navigation_{i}.png"
                                        page.screenshot(path=str(back_screenshot_path))
                                        print(f"Saved back navigation screenshot to {back_screenshot_path}")
                                        
                                        # Check if we're back on the orders page
                                        current_url = page.url
                                        if '/orders' in current_url or '/wmpurchasehistory' in current_url:
                                            print(f"Successfully returned to orders page: {current_url}")
                                        else:
                                            print(f"Back navigation didn't reach orders page, current URL: {current_url}")
                                            # If back button didn't work, try direct navigation
                                            page.goto(orders_page_url, timeout=self.timeout)
                                            page.wait_for_load_state('domcontentloaded', timeout=15000)
                                            page.wait_for_timeout(3000)
                                        
                                        # Print page HTML for debugging
                                        page_content = page.content()
                                        if "view-order-details-link" in page_content:
                                            print("Page contains 'view-order-details-link' text, but selectors failed to match")
                                        else:
                                            print("Page does not contain 'view-order-details-link' text")
                                        
                                        # Try multiple selectors to find order links
                                        selectors_to_try = [
                                            '[data-automation-id^="view-order-details-link-"]',
                                            'button[data-automation-id*="view-order-details-link"]',
                                            'button:has-text("View details")',
                                            'button[aria-label^="View details for order number"]',
                                            # Try more generic selectors as fallbacks
                                            'button.w_hhLG',
                                            'button[type="button"]',
                                            'a:has-text("View")',
                                            '[aria-label*="View details"]'
                                        ]
                                        
                                        order_links = []
                                        for selector in selectors_to_try:
                                            try:
                                                print(f"Trying to find order links with selector: {selector}")
                                                links = page.query_selector_all(selector)
                                                if links and len(links) > 0:
                                                    print(f"Found {len(links)} order links with selector: {selector}")
                                                    order_links = links
                                                    break
                                            except Exception as e:
                                                print(f"Error with selector {selector}: {e}")
                                        
                                        print(f"Found {len(order_links)} order links")
                                        
                                        if len(order_links) <= 1:
                                            print("Still not enough order links found, trying alternative navigation...")
                                            
                                            # Try direct navigation to different URLs
                                            urls_to_try = [
                                                'https://www.walmart.com/orders',
                                                'https://www.walmart.com/account/wmpurchasehistory'
                                            ]
                                            
                                            for url in urls_to_try:
                                                try:
                                                    print(f"Trying direct navigation to: {url}")
                                                    page.goto(url, timeout=self.timeout)
                                                    page.wait_for_load_state('domcontentloaded', timeout=15000)
                                                    try:
                                                        page.wait_for_load_state('networkidle', timeout=15000)
                                                    except:
                                                        pass
                                                    page.wait_for_timeout(3000)
                                                    
                                                    # Take a screenshot after navigation
                                                    nav_screenshot_path = self.output_dir / f"walmart_after_nav_to_{url.split('/')[-1]}_{i}.png"
                                                    page.screenshot(path=str(nav_screenshot_path))
                                                    print(f"Saved navigation screenshot to {nav_screenshot_path}")
                                                    
                                                    # Try all selectors one more time
                                                    for selector in selectors_to_try:
                                                        try:
                                                            links = page.query_selector_all(selector)
                                                            if links and len(links) > 1:
                                                                print(f"Found {len(links)} order links with selector {selector} at URL {url}")
                                                                order_links = links
                                                                break
                                                        except Exception as e:
                                                            print(f"Error with selector {selector} at URL {url}: {e}")
                                                    
                                                    if len(order_links) > 1:
                                                        print(f"Successfully found {len(order_links)} order links at URL {url}")
                                                        break
                                                except Exception as url_e:
                                                    print(f"Error navigating to {url}: {url_e}")
                                            
                                            print(f"Found {len(order_links)} order links after recovery attempts")
                                        # Skip this order and move to the next one
                                        i += 1
                                        page_orders_processed += 1
                                    except Exception as e:
                                        print(f"Error recovering after error: {e}")
                                        # Try one last approach - go to account page first
                                        try:
                                            print("Trying final recovery approach...")
                                            page.goto('https://www.walmart.com/orders', timeout=self.timeout)
                                            page.wait_for_load_state('domcontentloaded', timeout=15000)
                                            page.wait_for_timeout(2000)
                                            
                                            page.goto('https://www.walmart.com/account/wmpurchasehistory', timeout=self.timeout)
                                            page.wait_for_load_state('domcontentloaded', timeout=15000)
                                            page.wait_for_timeout(3000)
                                            
                                            print(f"Found {len(order_links)} order links after final recovery attempt")
                                            
                                            # Skip to the next order
                                            i += 1
                                            page_orders_processed += 1
                                        except Exception as final_error:
                                            print(f"All recovery attempts failed: {final_error}")
                                            break
                                except Exception as e:
                                    print(f"Error processing order {i+1}: {e}")
                                    # Take a screenshot for debugging
                                    screenshot_path = self.output_dir / f"walmart_order_error_{i+1}.png"
                                    page.screenshot(path=str(screenshot_path))
                                    print(f"Saved error screenshot to {screenshot_path}")
                                    
                                    # Try to continue with the next order
                                    i += 1
                                    page_orders_processed += 1
                            except Exception as outer_e:
                                print(f"Unexpected error in order processing loop: {outer_e}")
                                break
                        
                        print(f"Finished processing all orders on page {current_page}")
                        processed_orders = page_orders_processed
                        total_orders_processed += page_orders_processed
                    
                    # Check if there are more pages to process
                    print("Checking for next page...")
                    has_more_pages = False
                    
                    # Method 1: Look for a "Next" button
                    next_page_selectors = [
                        '[data-automation-id="next-pages-button"]',
                        'button:has-text("Next")',
                        'a:has-text("Next")',
                        '[aria-label="Next page"]',
                        '.next-page',
                        'li.next a'
                    ]
                    
                    # Wait longer for page to fully load before checking for next page
                    try:
                        print("Waiting for page to fully load before checking pagination...")
                        page.wait_for_load_state('domcontentloaded', timeout=15000)
                        page.wait_for_load_state('networkidle', timeout=15000)
                        # Additional wait to ensure JavaScript has fully executed
                        page.wait_for_timeout(8000)  # Increased from 5000 to 8000 ms
                        
                        # Take a screenshot to verify page state
                        pagination_check_screenshot = self.output_dir / f"walmart_pagination_check_page_{current_page}.png"
                        page.screenshot(path=str(pagination_check_screenshot))
                        print(f"Saved pagination check screenshot to {pagination_check_screenshot}")
                        
                        # Check for page content to verify we're on an orders page
                        page_content = page.content()
                        if "order-details" in page_content or "view-order-details" in page_content:
                            print("Verified page contains order details content")
                        else:
                            print("WARNING: Page may not contain order details content")
                    except Exception as e:
                        print(f"Warning: Wait for page load during pagination check: {e}")
                    
                    # First, try to find page number buttons
                    try:
                        print("Looking for page number buttons...")
                        # Try to find page number elements
                        page_buttons = page.query_selector_all('[data-automation-id^="page-"]')
                        if not page_buttons or len(page_buttons) == 0:
                            # Try alternative selectors for page buttons
                            page_buttons = page.query_selector_all('.page-select-dropdown-option')
                            if not page_buttons or len(page_buttons) == 0:
                                page_buttons = page.query_selector_all('button[data-testid^="pagination-button-"]')
                        
                        if page_buttons and len(page_buttons) > 0:
                            print(f"Found {len(page_buttons)} page number buttons")
                            
                            # Try to find the next page button
                            for button in page_buttons:
                                try:
                                    button_text = button.inner_text().strip()
                                    print(f"Found page button with text: '{button_text}'")
                                    
                                    # Try to determine if this is the next page button
                                    if button_text.isdigit() and int(button_text) == current_page + 1:
                                        print(f"Found next page button ({button_text})")
                                        print("Clicking on next page button...")
                                        
                                        # Click the button
                                        button.click()
                                        page.wait_for_load_state('domcontentloaded', timeout=15000)
                                        try:
                                            page.wait_for_load_state('networkidle', timeout=15000)
                                        except Exception as e:
                                            print(f"Network idle timeout after page button click (not critical): {e}")
                                        
                                        # Wait longer after clicking
                                        page.wait_for_timeout(10000)  # 10 seconds wait
                                        
                                        # Take a screenshot after navigation
                                        next_page_screenshot = self.output_dir / f"walmart_next_page_button_{button_text}.png"
                                        page.screenshot(path=str(next_page_screenshot))
                                        print(f"Saved next page navigation screenshot to {next_page_screenshot}")
                                        
                                        # Update page counter and continue
                                        current_page += 1
                                        has_more_pages = True
                                        break
                                except Exception as e:
                                    print(f"Error checking page button: {e}")
                            
                            # If we found and clicked a page button, continue to next iteration
                            if has_more_pages:
                                continue
                    except Exception as e:
                        print(f"Error trying to navigate using page number buttons: {e}")
                    
                    # If page number navigation didn't work, try the next button
                    for selector in next_page_selectors:
                        try:
                            next_button = page.query_selector(selector)
                            if next_button:
                                print(f"Found next page button with selector: {selector}")
                                # Check if the button is disabled
                                is_disabled = next_button.get_attribute('disabled') == 'true' or next_button.get_attribute('aria-disabled') == 'true'
                                if not is_disabled:
                                    print("Next button is enabled, clicking to navigate to next page")
                                    next_button.click()
                                    page.wait_for_load_state('domcontentloaded', timeout=20000)
                                    page.wait_for_load_state('load', timeout=20000)
                                    current_page += 1
                                    has_more_pages = True
                                    
                                    # Take a screenshot after navigation
                                    next_page_screenshot = self.output_dir / f"walmart_next_page_{current_page}.png"
                                    page.screenshot(path=str(next_page_screenshot))
                                    print(f"Saved next page screenshot to {next_page_screenshot}")
                                    break
                                else:
                                    print("Next button is disabled, no more pages")
                        except Exception as e:
                            print(f"Error with next page selector {selector}: {e}")
                    
                    # Break the pagination loop if we've processed too many pages (safety measure)
                    if current_page > 10:  # Limit to 10 pages as a safety measure
                        print("Reached maximum page limit (10), stopping pagination")
                        has_more_pages = False
                    
                    print(f"Processed {processed_orders} orders on current page, {total_orders_processed} orders total")
                    if has_more_pages:
                        print(f"Moving to page {current_page}")
                    else:
                        print("No more pages to process")
                
                print(f"Finished processing all orders across {current_page} pages. Total orders processed: {total_orders_processed}")
            except TimeoutError as e:
                print(f"Timeout error: {e}")
                print("The operation took too long to complete. This could be due to slow internet connection or website changes.")
                # Save a screenshot for debugging
                try:
                    screenshot_path = self.output_dir / "walmart_timeout_error.png"
                    page.screenshot(path=str(screenshot_path))
                    print(f"Saved error screenshot to {screenshot_path}")
                except:
                    pass
            except Exception as e:
                print(f"Error during Walmart scraping: {e}")
                # Save a screenshot for debugging
                try:
                    screenshot_path = self.output_dir / "walmart_error.png"
                    page.screenshot(path=str(screenshot_path))
                    print(f"Saved error screenshot to {screenshot_path}")
                except:
                    pass
            finally:
                if browser:
                    browser.close()

    def scrape_amazon(self):
        if not self.config.amazon_credentials:
            print(f"No Amazon credentials for {self.config.name}")
            return

        with sync_playwright() as playwright:
            browser, context = self._setup_browser(
                playwright, 
                self.amazon_session_file,
                self.amazon_profile_dir if self.persistent_browser else None
            )
            page = context.new_page()
            
            try:
                if self.pure_manual:
                    print("\n=== PURE MANUAL MODE ===")
                    print("Please follow these steps in the browser window:")
                    print("1. Navigate to https://www.amazon.com")
                    print("2. Click on 'Account & Lists' or 'Sign In'")
                    print("3. Log in with your credentials")
                    print("4. Complete any verification challenges")
                    print("5. Navigate to https://www.amazon.com/gp/your-account/order-history when ready")
                    print("Type 'continue' when you've completed these steps, or 'skip' to abort.")
                    print("==========================================\n")
                    
                    # Open Amazon homepage
                    page.goto('https://www.amazon.com', timeout=self.timeout)
                    
                    # Wait for user to complete manual login
                    user_input = ""
                    while user_input not in ['continue', 'skip']:
                        user_input = input("Enter 'continue' when ready or 'skip' to abort: ").lower()
                        
                    if user_input == 'skip':
                        print("Login attempt aborted by user.")
                        return
                    
                    # Navigate to orders page
                    print("Navigating to orders page...")
                    page.goto('https://www.amazon.com/gp/your-account/order-history', timeout=self.timeout)
                else:
                    print("Navigating to Amazon login page...")
                    # Login to Amazon - use a longer timeout for initial page load
                    initial_load_timeout = max(self.timeout * 2, 60000)  # At least 60 seconds
                    print(f"Using extended timeout of {initial_load_timeout/1000} seconds for initial page load...")
                    
                    try:
                        page.goto('https://www.amazon.com/signin', timeout=initial_load_timeout)
                    except TimeoutError:
                        print("Initial page load timed out, but we'll try to continue anyway...")
                        # Take a screenshot to see what happened
                        screenshot_path = self.output_dir / "amazon_initial_load_error.png"
                        page.screenshot(path=str(screenshot_path))
                        print(f"Saved initial load error screenshot to {screenshot_path}")
                    
                    # Wait for the page to stabilize
                    print("Waiting for page to stabilize...")
                    try:
                        page.wait_for_load_state('networkidle', timeout=self.timeout)
                    except:
                        print("Page didn't reach network idle state, continuing anyway...")
                    
                    # Check if we're already logged in
                    if "nav-link-accountList" in page.content() or "Your Account" in page.content():
                        print("Already logged into Amazon (session restored)")
                    else:
                        print("Looking for login form...")
                        
                        # Check if the login form is visible
                        login_form_visible = False
                        try:
                            login_form_visible = page.wait_for_selector('#ap_email', timeout=self.timeout, state='visible') is not None
                        except:
                            print("Login form not immediately visible")
                        
                        if not login_form_visible:
                            # Try navigating directly to the login page again
                            print("Trying to navigate to login page again...")
                            page.goto('https://www.amazon.com/ap/signin?openid.pape.max_auth_age=0&openid.return_to=https%3A%2F%2Fwww.amazon.com%2F%3Fref_%3Dnav_signin&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.assoc_handle=usflex&openid.mode=checkid_setup&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0', timeout=self.timeout)
                            try:
                                page.wait_for_selector('#ap_email', timeout=self.timeout)
                            except:
                                print("Still can't find login form. Taking a screenshot for debugging...")
                                screenshot_path = self.output_dir / "amazon_login_form_error.png"
                                page.screenshot(path=str(screenshot_path))
                                print(f"Saved login form error screenshot to {screenshot_path}")
                                
                                if self.manual_mode:
                                    print("\n=== MANUAL INTERVENTION NEEDED ===")
                                    print("The script couldn't find the login form automatically.")
                                    print("Please navigate to the login page manually in the browser.")
                                    print("Type 'continue' when you're on the login page, or 'skip' to abort.")
                                    print("==========================================\n")
                                    
                                    user_input = ""
                                    while user_input not in ['continue', 'skip']:
                                        user_input = input("Enter 'continue' when ready or 'skip' to abort: ").lower()
                                        
                                    if user_input == 'skip':
                                        print("Login attempt aborted by user.")
                                        return
                                else:
                                    print("Cannot proceed without login form. Aborting.")
                                    return
                    
                    print("Filling in Amazon login credentials...")
                    try:
                        # Wait for the email field to be visible
                        page.wait_for_selector('#ap_email', timeout=self.timeout)
                        page.fill('#ap_email', self.config.amazon_credentials.username)
                        
                        print("Clicking continue button...")
                        page.click('#continue')
                        
                        # Wait for the password field to be visible
                        page.wait_for_selector('#ap_password', timeout=self.timeout)
                        page.fill('#ap_password', self.config.amazon_credentials.password)
                        
                        print("Clicking sign-in button...")
                        page.click('#signInSubmit')
                    except Exception as e:
                        print(f"Error during login form interaction: {e}")
                        screenshot_path = self.output_dir / "amazon_login_interaction_error.png"
                        page.screenshot(path=str(screenshot_path))
                        print(f"Saved login interaction error screenshot to {screenshot_path}")
                        
                        if not self.manual_mode:
                            print("Switching to manual mode due to login form interaction error...")
                            self.manual_mode = True
                    
                    # Special handling for Amazon verification
                    print("\n=== AMAZON VERIFICATION ===")
                    print("If you see a verification challenge:")
                    print("1. Complete any CAPTCHA puzzles in the browser")
                    print("2. If prompted for a verification code, check your email or phone")
                    print("3. Enter the code you receive")
                    print("4. If you see 'unusual activity' warnings, approve the login")
                    print("==========================================\n")
                    
                    if self.manual_mode:
                        print("\n=== MANUAL AUTHENTICATION MODE ===")
                        print("Please complete any verification steps in the browser window.")
                        print("Type 'continue' and press Enter when you've finished logging in.")
                        print("Type 'skip' if you want to abort this login attempt.")
                        print("==========================================\n")
                        
                        # Wait for user to type 'continue' or 'skip'
                        user_input = ""
                        while user_input not in ['continue', 'skip']:
                            user_input = input("Enter 'continue' when ready or 'skip' to abort: ").lower()
                            
                        if user_input == 'skip':
                            print("Login attempt aborted by user.")
                            return
                    else:
                        print("\n=== MANUAL AUTHENTICATION REQUIRED ===")
                        print("Please complete any verification steps in the browser window.")
                        print("The script will wait for 1 minute or until you complete the login.")
                        print("After logging in, the script will continue automatically.")
                        print("==========================================\n")
                        
                        # Wait for manual intervention
                        page.wait_for_timeout(self.manual_timeout)
                
                # Check if login was successful
                if "nav-link-accountList" in page.content() or "Your Account" in page.content():
                    print("Successfully logged into Amazon")
                    # Save the session for future use
                    self._save_session(context, self.amazon_session_file)
                else:
                    # Try to navigate to orders page anyway
                    print("Attempting to navigate to orders page...")
                    page.goto('https://www.amazon.com/gp/your-account/order-history', timeout=self.timeout)
                    page.wait_for_load_state('networkidle', timeout=self.timeout)
                    
                    # Check if we're on the orders page
                    if "order-history" not in page.url:
                        print("Login unsuccessful or orders page not accessible.")
                        print("Please check if you're logged in and try again.")
                        
                        # Save a screenshot for debugging
                        screenshot_path = self.output_dir / "amazon_login_error.png"
                        page.screenshot(path=str(screenshot_path))
                        print(f"Saved login error screenshot to {screenshot_path}")
                        
                        # Try direct navigation to Amazon homepage
                        print("Attempting to navigate to Amazon homepage...")
                        page.goto('https://www.amazon.com/', timeout=self.timeout)
                        page.wait_for_load_state('networkidle', timeout=self.timeout)
                        
                        # Check if we can access the account menu
                        if "nav-link-accountList" in page.content() or "Your Account" in page.content():
                            print("Successfully logged in (verified via homepage)")
                            # Save the session for future use
                            self._save_session(context, self.amazon_session_file)
                        else:
                            return

                print("Navigating to orders page...")
                # Navigate to orders page
                page.goto('https://www.amazon.com/gp/your-account/order-history', timeout=self.timeout)
                page.wait_for_load_state('networkidle', timeout=self.timeout)

                # Create date-based directory
                date_dir = self.output_dir / datetime.now().strftime("%Y-%m")
                date_dir.mkdir(exist_ok=True)

                # Setup download handler
                page.on('download', lambda download: download.save_as(
                    date_dir / f"amazon_invoice_{download.suggested_filename}"
                ))

                print("Looking for invoice links...")
                # Find and click invoice links
                invoice_links = page.query_selector_all('a:has-text("Invoice")')
                if not invoice_links:
                    print("No invoice links found. The page structure might have changed or there are no invoices.")
                    
                    # Save a screenshot for debugging
                    screenshot_path = date_dir / "amazon_debug_screenshot.png"
                    page.screenshot(path=str(screenshot_path))
                    print(f"Saved debug screenshot to {screenshot_path}")
                else:
                    print(f"Found {len(invoice_links)} invoice links")
                    for i, link in enumerate(invoice_links):
                        print(f"Clicking invoice link {i+1}/{len(invoice_links)}")
                        link.click()
                        page.wait_for_timeout(2000)  # Wait for download to start

            except TimeoutError as e:
                print(f"Timeout error: {e}")
                print("The operation took too long to complete. This could be due to slow internet connection or website changes.")
                # Save a screenshot for debugging
                try:
                    screenshot_path = self.output_dir / "amazon_timeout_error.png"
                    page.screenshot(path=str(screenshot_path))
                    print(f"Saved error screenshot to {screenshot_path}")
                except:
                    pass
            except Exception as e:
                print(f"Error during Amazon scraping: {e}")
                # Save a screenshot for debugging
                try:
                    screenshot_path = self.output_dir / "amazon_error.png"
                    page.screenshot(path=str(screenshot_path))
                    print(f"Saved error screenshot to {screenshot_path}")
                except:
                    pass
            finally:
                if browser:
                    browser.close()

    def check_walmart_login(self, page):
        """Check if logged in to Walmart."""
        try:
            # Wait longer for any login processes to complete
            print("Waiting for login processes to complete...")
            page.wait_for_timeout(10000)  # 10 second delay to ensure login completes
            
            # Check for account-related elements that indicate logged-in state
            logged_in_selectors = [
                '[data-automation-id="account-dropdown"]',
                '[data-automation-id="account-button"]',
                '[data-testid="account-dropdown"]',
                '[data-testid="account-button"]',
                '[data-testid="account-username"]',
                '[data-testid="sign-out"]',
                'button:has-text("Account")',
                'button:has-text("My Account")',
                'a:has-text("Account")',
                'a:has-text("My Account")',
                'text="Account Home"',
                'text="Your Account"',
                'text="Sign Out"'
            ]
            
            # First check if we're on an account-related page
            current_url = page.url
            if '/account' in current_url or '/myaccount' in current_url:
                print(f"On account page: {current_url} - likely logged in")
                return True
                
            # Check for visible selectors
            for selector in logged_in_selectors:
                try:
                    if page.is_visible(selector, timeout=3000):
                        print(f"Detected logged-in state using selector: {selector}")
                        return True
                except Exception:
                    pass
            
            # Try JavaScript approach as a fallback
            try:
                js_result = page.evaluate('''
                    () => {
                        // Check for account-related elements
                        const accountElements = document.querySelectorAll('[data-testid*="account"], [data-automation-id*="account"]');
                        if (accountElements.length > 0) {
                            return true;
                        }
                        
                        // Check for sign-out links
                        const signOutElements = document.querySelectorAll('a[href*="signout"], a[href*="logout"]');
                        if (signOutElements.length > 0) {
                            return true;
                        }
                        
                        // Check page content for account-related text
                        const pageText = document.body.innerText;
                        if (pageText.includes("Sign Out") || 
                            pageText.includes("Your Account") || 
                            pageText.includes("Account Home")) {
                            return true;
                        }
                        
                        return false;
                    }
                ''')
                
                if js_result:
                    print("Detected logged-in state using JavaScript approach")
                    return True
            except Exception as e:
                print(f"Error in JavaScript login check: {e}")
            
            # If we get here, we're probably not logged in
            print("No login indicators found, assuming not logged in")
            return False
        except Exception as e:
            print(f"Error checking login status: {e}")
            return False

if __name__ == "__main__":
    # Example usage
    config = CompanyConfig(
        name="TestCompany",
        walmart_credentials=WebsiteCredentials(
            username="test@example.com",
            password="password"
        ),
        amazon_credentials=WebsiteCredentials(
            username="test@example.com",
            password="password"
        ),
        output_directory="./downloads/TestCompany"
    )

    scraper = WebScraper(config, manual_mode=True, pure_manual=True, persistent_browser=True, incognito_mode=False)
    scraper.scrape_walmart()
    scraper.scrape_amazon()
