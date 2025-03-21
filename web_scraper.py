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

    def _handle_download(self, download, directory, prefix=""):
        """Handle a download from a page, saving it to the specified directory with an optional prefix."""
        try:
            # Create the directory if it doesn't exist
            directory.mkdir(parents=True, exist_ok=True)
            
            # Get the suggested filename from the download
            filename = download.suggested_filename
            
            # Add prefix if specified
            if prefix:
                filename = f"{prefix}{filename}"
            
            # Save the file
            download_path = directory / filename
            download.save_as(download_path)
            
            print(f"Downloaded file: {filename} to {directory}")
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
            except Exception as e:
                print(f"Error verifying PDF content: {e}")
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
    
    def _extract_amazon_purchase_date(self, page):
        """Extract purchase date from Amazon order page."""
        try:
            # Try multiple selectors to find the purchase date element
            date_selectors = [
                '.order-date-invoice-item',
                '.a-color-secondary:has-text("Order placed")',
                '.order-date',
                '.a-box-inner .a-section .a-span4 .a-color-secondary',
                'span:has-text("Order placed:")',
                '.order-info:has-text("Order placed")'
            ]
            
            for selector in date_selectors:
                try:
                    date_element = page.query_selector(selector)
                    if date_element:
                        date_text = date_element.text_content()
                        print(f"Found date text: {date_text}")
                        
                        # Try to extract date with regex
                        date_patterns = [
                            r'Order placed:\s*(\w+\s+\d+,\s*\d{4})',
                            r'Order placed\s*(\w+\s+\d+,\s*\d{4})',
                            r'Ordered on\s*(\w+\s+\d+,\s*\d{4})',
                            r'(\w+\s+\d+,\s*\d{4})',
                            r'(\d{1,2}/\d{1,2}/\d{2,4})',
                            r'(\d{1,2}-\d{1,2}-\d{2,4})'
                        ]
                        
                        for pattern in date_patterns:
                            match = re.search(pattern, date_text)
                            if match:
                                date_str = match.group(1)
                                print(f"Extracted date string: {date_str}")
                                
                                # Try multiple date formats
                                date_formats = [
                                    '%B %d, %Y',  # January 1, 2023
                                    '%b %d, %Y',  # Jan 1, 2023
                                    '%m/%d/%Y',   # 01/01/2023
                                    '%m/%d/%y',   # 01/01/23
                                    '%m-%d-%Y',   # 01-01-2023
                                    '%m-%d-%y'    # 01-01-23
                                ]
                                
                                for date_format in date_formats:
                                    try:
                                        purchase_date = datetime.strptime(date_str, date_format)
                                        print(f"Parsed purchase date: {purchase_date}")
                                        return purchase_date
                                    except ValueError:
                                        continue
                except Exception as e:
                    print(f"Error with date selector {selector}: {e}")
            
            # Try JavaScript approach as a fallback
            try:
                js_result = page.evaluate("""() => {
                    // Look for elements with date-related text
                    const dateElements = document.querySelectorAll('*');
                    for (const elem of dateElements) {
                        const text = elem.textContent;
                        if (text && (
                            text.includes('Order placed') || 
                            text.includes('Ordered on') ||
                            text.includes('Order date')
                        )) {
                            return text;
                        }
                    }
                    return null;
                }""")
                
                if js_result:
                    print(f"Found date text via JavaScript: {js_result}")
                    
                    # Try to extract date with regex
                    date_patterns = [
                        r'Order placed:\s*(\w+\s+\d+,\s*\d{4})',
                        r'Order placed\s*(\w+\s+\d+,\s*\d{4})',
                        r'Ordered on\s*(\w+\s+\d+,\s*\d{4})',
                        r'(\w+\s+\d+,\s*\d{4})',
                        r'(\d{1,2}/\d{1,2}/\d{2,4})',
                        r'(\d{1,2}-\d{1,2}-\d{2,4})'
                    ]
                    
                    for pattern in date_patterns:
                        match = re.search(pattern, js_result)
                        if match:
                            date_str = match.group(1)
                            print(f"Extracted date string from JavaScript: {date_str}")
                            
                            # Try multiple date formats
                            date_formats = [
                                '%B %d, %Y',  # January 1, 2023
                                '%b %d, %Y',  # Jan 1, 2023
                                '%m/%d/%Y',   # 01/01/2023
                                '%m/%d/%y',   # 01/01/23
                                '%m-%d-%Y',   # 01-01-2023
                                '%m-%d-%y'    # 01-01-23
                            ]
                            
                            for date_format in date_formats:
                                try:
                                    purchase_date = datetime.strptime(date_str, date_format)
                                    print(f"Parsed purchase date from JavaScript: {purchase_date}")
                                    return purchase_date
                                except ValueError:
                                    continue
            except Exception as e:
                print(f"Error in JavaScript date extraction: {e}")
            
            # If we get here, we couldn't find a date
            print("Could not extract purchase date, using current date")
            return datetime.now()
        except Exception as e:
            print(f"Error extracting purchase date: {e}")
            return datetime.now()

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
                        '[data-automation-id*="view-order-details-"]',
                        '[data-automation-id*="order-details"]',
                        '[data-testid*="order-details"]',
                        'a[href*="order-details"]',
                        'a[href*="order/details"]',
                        'button:has-text("View details")',
                        'a:has-text("View details")',
                        'button:has-text("Order details")',
                        'a:has-text("Order details")',
                        'button:has-text("View order")',
                        'a:has-text("View order")',
                        '[aria-label*="View details"]',
                        '[aria-label*="order details"]',
                        '[data-testid*="order-card"]',
                        '[data-automation-id*="order-card"]'
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
                    
                    # If no buttons found, try a more aggressive approach by looking for any clickable elements
                    if not view_details_buttons:
                        print("No specific order buttons found, trying to find any potential order elements...")
                        try:
                            # Look for any elements that might be order cards or containers
                            potential_order_elements = page.query_selector_all('[class*="order"], [class*="purchase"], [id*="order"], [id*="purchase"]')
                            if potential_order_elements:
                                print(f"Found {len(potential_order_elements)} potential order elements")
                                
                                # Try to find clickable elements within these containers
                                for elem in potential_order_elements:
                                    try:
                                        clickable = elem.query_selector('a, button')
                                        if clickable:
                                            view_details_buttons.append(clickable)
                                    except:
                                        pass
                                
                                if view_details_buttons:
                                    print(f"Found {len(view_details_buttons)} clickable elements within order containers")
                        except Exception as e:
                            print(f"Error trying to find generic order elements: {e}")
                    
                    # Take a screenshot of the page for manual inspection
                    screenshot_path = self.output_dir / f"walmart_orders_page_{current_page}_detection.png"
                    page.screenshot(path=str(screenshot_path))
                    print(f"Saved order detection screenshot to {screenshot_path}")
                    
                    # Save the HTML content for debugging
                    html_path = self.output_dir / f"walmart_orders_page_{current_page}.html"
                    with open(html_path, 'w', encoding='utf-8') as f:
                        f.write(page.content())
                    print(f"Saved page HTML to {html_path} for debugging")
                    
                    if not view_details_buttons:
                        print("No order details buttons found. Taking a screenshot for debugging...")
                        
                        # Check the HTML content for debugging
                        print("Checking page content for debugging...")
                        page_content = page.content()
                        if "order details" in page_content.lower() or "view order" in page_content.lower():
                            print("Page content contains 'order details' or 'view order' text, but selectors failed to match")
                            
                            # Try JavaScript approach to find and click order links
                            print("Attempting JavaScript approach to find order links...")
                            try:
                                # Use JavaScript to find elements with text containing "View" and "order"
                                js_result = page.evaluate("""() => {
                                    const elements = Array.from(document.querySelectorAll('a, button'));
                                    const orderLinks = elements.filter(el => {
                                        const text = el.innerText.toLowerCase();
                                        return (text.includes('view') && (text.includes('order') || text.includes('details')));
                                    });
                                    return orderLinks.length;
                                }""")
                                
                                print(f"JavaScript found {js_result} potential order links")
                                
                                if js_result > 0:
                                    # We found links via JavaScript, now use them
                                    print("Found order links via JavaScript, will use them for processing")
                                    has_js_links = True
                                else:
                                    has_js_links = False
                            except Exception as e:
                                print(f"JavaScript approach failed: {e}")
                                has_js_links = False
                            
                            # If we found links via JavaScript, don't skip this page
                            if has_js_links:
                                # Process orders using JavaScript
                                print("Processing orders using JavaScript approach...")
                                
                                # Get the number of order links
                                num_links = page.evaluate("""() => {
                                    const elements = Array.from(document.querySelectorAll('a, button'));
                                    const orderLinks = elements.filter(el => {
                                        const text = el.innerText.toLowerCase();
                                        return (text.includes('view') && (text.includes('order') || text.includes('details')));
                                    });
                                    return orderLinks.length;
                                }""")
                                
                                # Process each order link
                                for i in range(num_links):
                                    try:
                                        print(f"Processing JavaScript-found order {i+1}/{num_links}")
                                        
                                        # Click the link using JavaScript
                                        page.evaluate(f"""(index) => {{
                                            const elements = Array.from(document.querySelectorAll('a, button'));
                                            const orderLinks = elements.filter(el => {{
                                                const text = el.innerText.toLowerCase();
                                                return (text.includes('view') && (text.includes('order') || text.includes('details')));
                                            }});
                                            if (orderLinks[index]) orderLinks[index].click();
                                        }}""", i)
                                        
                                        # Wait for navigation
                                        page.wait_for_load_state("domcontentloaded", timeout=self.timeout)
                                        page.wait_for_timeout(2000)
                                        
                                        # Extract purchase date and process the invoice
                                        purchase_date = self._extract_purchase_date(page)
                                        
                                        # Get order number if possible
                                        try:
                                            order_number = "unknown"
                                            order_number_elements = page.query_selector_all('div:has-text("Order#"), span:has-text("Order#")')
                                            for elem in order_number_elements:
                                                text = elem.text_content()
                                                match = re.search(r'Order\s+#?\s*(\w+)', text)
                                                if match:
                                                    order_number = match.group(1)
                                                    print(f"Found order number: {order_number}")
                                                    break
                                        except:
                                            pass
                                        
                                        # Set the current order number for the download handler
                                        self.current_order_number = order_number
                                        
                                        if purchase_date:
                                            # Create directory based on purchase date
                                            invoice_dir = self._get_invoice_directory(self.config.name, purchase_date)
                                            print(f"Saving invoice to directory: {invoice_dir}")
                                            
                                            # Check if invoice already exists
                                            if self._check_invoice_exists(invoice_dir, order_number):
                                                print("Invoice already exists. Assuming all older invoices have been processed.")
                                                print("Ending the process to avoid redundant processing.")
                                                return  # End the entire scraping process
                                        else:
                                            print("Could not extract purchase date, using default directory")
                                            invoice_dir = self._get_invoice_directory(self.config.name)
                                            print(f"Saving invoice to directory: {invoice_dir}")
                                            
                                            # Also check if invoice exists in the fallback directory
                                            if self._check_invoice_exists(invoice_dir, order_number):
                                                print("Invoice already exists in fallback directory. Ending the process.")
                                                return  # End the entire scraping process
                                        
                                        # Download the invoice
                                        print("Downloading using page.pdf()")
                                        
                                        # Create filename with purchase date (MM-DD) instead of download timestamp
                                        if purchase_date:
                                            date_str = purchase_date.strftime('%m-%d')
                                            pdf_path = invoice_dir / f"walmart_invoice_{order_number}_{date_str}.pdf"
                                        else:
                                            # Fallback to current date if purchase date couldn't be extracted
                                            current_date = datetime.now()
                                            date_str = current_date.strftime('%m-%d')
                                            pdf_path = invoice_dir / f"walmart_invoice_{order_number}_{date_str}_unknown_purchase_date.pdf"
                                        
                                        try:
                                            # Try to scroll through the page
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
                                            
                                            # Generate PDF
                                            pdf_data = page.pdf(
                                                format="Letter",
                                                print_background=True,
                                                margin={"top": "0.5in", "right": "0.5in", "bottom": "0.5in", "left": "0.5in"},
                                                scale=0.9
                                            )
                                            
                                            with open(pdf_path, 'wb') as f:
                                                f.write(pdf_data)
                                            print(f"Successfully saved PDF to {pdf_path}")
                                            
                                            # Verify the PDF
                                            self._verify_pdf_download(pdf_path)
                                        except Exception as e:
                                            print(f"Error saving PDF: {e}")
                                        
                                        # Go back to orders page
                                        print("Navigating back to orders page...")
                                        page.goto('https://www.walmart.com/orders', timeout=self.timeout)
                                        page.wait_for_load_state('domcontentloaded', timeout=15000)
                                        page.wait_for_timeout(5000)
                                        
                                    except Exception as e:
                                        print(f"Error processing JavaScript-found order {i+1}: {e}")
                                        # Try to go back to orders page
                                        try:
                                            page.goto('https://www.walmart.com/orders', timeout=self.timeout)
                                            page.wait_for_load_state('domcontentloaded', timeout=15000)
                                            page.wait_for_timeout(5000)
                                        except:
                                            pass
                                
                                # After processing all JavaScript-found orders, move to next page
                                current_page += 1
                                continue
                        else:
                            print("Page content does not contain expected order-related text")
                        
                        # If no orders found on first page, try to navigate to next page
                        if current_page == 1:
                            print("No orders found on first page, will try to navigate to next page")
                            current_page += 1
                            
                            # Try direct navigation to page 2
                            try:
                                print("Trying direct navigation to page 2...")
                                page.goto('https://www.walmart.com/orders?page=2', timeout=self.timeout)
                                page.wait_for_load_state('domcontentloaded', timeout=15000)
                                page.wait_for_timeout(5000)
                                continue
                            except Exception as e:
                                print(f"Error navigating to page 2: {e}")
                        else:
                            # Try to navigate to the next page even if no orders were found on this page
                            print(f"No orders found on page {current_page}, trying next page anyway")
                            current_page += 1
                            
                            # Try direct navigation to next page
                            try:
                                print(f"Trying direct navigation to page {current_page}...")
                                page.goto(f'https://www.walmart.com/orders?page={current_page}', timeout=self.timeout)
                                page.wait_for_load_state('domcontentloaded', timeout=15000)
                                page.wait_for_timeout(5000)
                                continue
                            except Exception as e:
                                print(f"Error navigating to page {current_page}: {e}")
                                
                                # If direct navigation fails, try the next page button
                                try:
                                    print("Trying to find and click next page button...")
                                    next_button = page.query_selector('button:has-text("Next"), a:has-text("Next"), [aria-label="Next page"]')
                                    if next_button:
                                        next_button.click()
                                        page.wait_for_load_state('domcontentloaded', timeout=15000)
                                        page.wait_for_timeout(5000)
                                        continue
                                except Exception as e:
                                    print(f"Error clicking next page button: {e}")
                                    
                                print("No more pages to process")
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
                                            print("Invoice already exists. Assuming all older invoices have been processed.")
                                            print("Ending the process to avoid redundant processing.")
                                            return  # End the entire scraping process
                                    else:
                                        print("Could not extract purchase date, using default directory")
                                        invoice_dir = self._get_invoice_directory(self.config.name)
                                        print(f"Saving invoice to directory: {invoice_dir}")
                                        
                                        # Also check if invoice exists in the fallback directory
                                        if self._check_invoice_exists(invoice_dir, order_number):
                                            print("Invoice already exists in fallback directory. Ending the process.")
                                            return  # End the entire scraping process
                                     
                                    # Process the invoice download using our existing code
                                    downloaded_invoices = 0
                                        
                                    # Third attempt: If no invoices were downloaded, try using page.pdf() as a fallback
                                    if downloaded_invoices == 0:
                                        print("Downloading using page.pdf()")
                                        
                                        # Create filename with purchase date (MM-DD) instead of download timestamp
                                        if purchase_date:
                                            date_str = purchase_date.strftime('%m-%d')
                                            pdf_path = invoice_dir / f"walmart_invoice_{order_number}_{date_str}.pdf"
                                        else:
                                            # Fallback to current date if purchase date couldn't be extracted
                                            current_date = datetime.now()
                                            date_str = current_date.strftime('%m-%d')
                                            pdf_path = invoice_dir / f"walmart_invoice_{order_number}_{date_str}_unknown_purchase_date.pdf"
                                        
                                        try:
                                            # Try to scroll through the page
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
                                            
                                            # Generate PDF
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
                                print(f"Found next page button using selector: {selector}")
                                
                                # Check if the button is disabled
                                is_disabled = False
                                try:
                                    parent_element = next_button.evaluate('node => node.parentElement')
                                    if parent_element:
                                        parent_class = parent_element.get_attribute('class') or ''
                                        if 'a-disabled' in parent_class:
                                            is_disabled = True
                                except:
                                    pass
                                
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
                            else:
                                print(f"No next page button found with selector: {selector}")
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
        """Scrape Amazon invoices."""
        print("\n=== Starting Amazon Scraping ===\n")
        
        # Initialize browser and context
        browser = None
        try:
            # Setup browser with appropriate options
            browser_type = 'chromium'
            if self.edge_mode:
                browser_type = 'chromium'
                
            browser_args = []
            # Add user agent for Microsoft Edge to reduce detection
            browser_args.append('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59')
            
            # Add additional headers to appear more like a regular browser
            browser_args.append('--accept-language=en-US,en;q=0.9')
            
            # Check if we should use a persistent browser profile
            if self.persistent_browser:
                print("Using persistent browser profile for Amazon")
                user_data_dir = self.output_dir / "amazon_browser_data"
                user_data_dir.mkdir(exist_ok=True)
                
                browser = self.playwright.chromium.launch_persistent_context(
                    user_data_dir=str(user_data_dir),
                    headless=not self.manual_mode,
                    args=browser_args,
                    ignore_https_errors=True
                )
                context = browser
                page = context.new_page()
            else:
                print("Using incognito browser for Amazon")
                browser = self.playwright.chromium.launch(headless=not self.manual_mode, args=browser_args)
                context = browser.new_context(
                    ignore_https_errors=True,
                    viewport={'width': 1280, 'height': 800}
                )
                page = context.new_page()
            
            # Set default timeout
            page.set_default_timeout(self.timeout)
            
            # Try to load a saved session if available and not in pure manual mode
            session_loaded = False
            if not self.pure_manual and Path(self.amazon_session_file).exists():
                try:
                    print("Attempting to load saved Amazon session...")
                    self._load_session(context, self.amazon_session_file)
                    
                    # Navigate to Amazon to check if the session is valid
                    page.goto('https://www.amazon.com/', timeout=self.timeout)
                    page.wait_for_load_state('networkidle', timeout=self.timeout)
                    
                    # Check if we're logged in
                    if "nav-link-accountList" in page.content() or "Your Account" in page.content():
                        print("Successfully loaded Amazon session, already logged in")
                        session_loaded = True
                    else:
                        print("Session loaded but not logged in, will proceed with login")
                except Exception as e:
                    print(f"Error loading Amazon session: {e}")
            
            # If session wasn't loaded or we're in pure manual mode, proceed with login
            if not session_loaded:
                # Navigate to Amazon login page
                print("Navigating to Amazon login page...")
                try:
                    page.goto('https://www.amazon.com/ap/signin?openid.pape.max_auth_age=0&openid.return_to=https%3A%2F%2Fwww.amazon.com%2F%3Fref_%3Dnav_signin&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.assoc_handle=usflex&openid.mode=checkid_setup&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0', timeout=self.timeout)
                    page.wait_for_load_state('networkidle', timeout=self.timeout)
                except Exception as e:
                    print(f"Error navigating to Amazon login page: {e}")
                    # Try a simpler URL as fallback
                    page.goto('https://www.amazon.com/ap/signin', timeout=self.timeout)
                    page.wait_for_load_state('networkidle', timeout=self.timeout)
                
                # Check if we need to handle login
                if "ap/signin" in page.url or "sign-in" in page.url:
                    print("On Amazon login page, proceeding with authentication")
                    
                    # Check if we're in pure manual mode
                    if self.pure_manual:
                        print("\n*** PURE MANUAL MODE ***")
                        print("Please log in to Amazon manually.")
                        print(f"You have {self.manual_timeout/1000} seconds to complete the login.")
                        print("The browser will wait for you to finish.\n")
                        
                        # Wait for manual intervention
                        page.wait_for_timeout(self.manual_timeout)
                    else:
                        # Try automated login first
                        try:
                            print("Attempting automated login...")
                            
                            # Find and fill email field
                            email_selectors = ['input[type="email"]', '#ap_email', 'input[name="email"]']
                            email_filled = False
                            
                            for selector in email_selectors:
                                try:
                                    if page.is_visible(selector):
                                        # Type email with random delays between characters
                                        email_input = page.query_selector(selector)
                                        if email_input:
                                            print("Found email field, entering email...")
                                            for char in self.amazon_credentials.username:
                                                email_input.type(char, delay=random.randint(50, 150))
                                                page.wait_for_timeout(random.randint(10, 50))
                                            
                                            # Find and click continue button
                                            continue_selectors = ['input[type="submit"]', '#continue', 'input[id="continue"]', 'span:has-text("Continue")']
                                            for continue_selector in continue_selectors:
                                                try:
                                                    if page.is_visible(continue_selector):
                                                        print("Clicking continue button...")
                                                        page.click(continue_selector)
                                                        page.wait_for_load_state('networkidle', timeout=10000)
                                                        email_filled = True
                                                        break
                                                except Exception as e:
                                                    print(f"Error clicking continue button with selector {continue_selector}: {e}")
                                            
                                            if email_filled:
                                                break
                                except Exception as e:
                                    print(f"Error with email selector {selector}: {e}")
                            
                            # Find and fill password field
                            password_selectors = ['input[type="password"]', '#ap_password', 'input[name="password"]']
                            for selector in password_selectors:
                                try:
                                    if page.is_visible(selector):
                                        # Type password with random delays between characters
                                        password_input = page.query_selector(selector)
                                        if password_input:
                                            print("Found password field, entering password...")
                                            for char in self.amazon_credentials.password:
                                                password_input.type(char, delay=random.randint(50, 150))
                                                page.wait_for_timeout(random.randint(10, 50))
                                            
                                            # Find and click sign-in button
                                            signin_selectors = ['input[type="submit"]', '#signInSubmit', 'input[id="signInSubmit"]', 'span:has-text("Sign-In")']
                                            for signin_selector in signin_selectors:
                                                try:
                                                    if page.is_visible(signin_selector):
                                                        print("Clicking sign-in button...")
                                                        page.click(signin_selector)
                                                        page.wait_for_load_state('networkidle', timeout=10000)
                                                        break
                                                except Exception as e:
                                                    print(f"Error clicking sign-in button with selector {signin_selector}: {e}")
                                            
                                            break
                                except Exception as e:
                                    print(f"Error with password selector {selector}: {e}")
                            
                            # Check for CAPTCHA or verification challenges
                            captcha_indicators = [
                                'captcha', 
                                'verification', 
                                'puzzle', 
                                'security challenge',
                                'authentication required'
                            ]
                            
                            page_content = page.content().lower()
                            if any(indicator in page_content for indicator in captcha_indicators):
                                print("\n*** CAPTCHA or verification detected ***")
                                print("Please complete the verification manually.")
                                print(f"You have {self.manual_timeout/1000} seconds to complete the verification.")
                                print("The browser will wait for you to finish.\n")
                                
                                # Take a screenshot for debugging
                                screenshot_path = self.output_dir / "amazon_captcha.png"
                                page.screenshot(path=str(screenshot_path))
                                print(f"Saved CAPTCHA screenshot to {screenshot_path}")
                                
                                # Wait for manual intervention
                                page.wait_for_timeout(self.manual_timeout)
                        except Exception as e:
                            print(f"Error during automated login: {e}")
                            print("\n*** Switching to manual login mode ***")
                            print("Please log in to Amazon manually.")
                            print(f"You have {self.manual_timeout/1000} seconds to complete the login.")
                            print("The browser will wait for you to finish.\n")
                            
                            # Take a screenshot for debugging
                            screenshot_path = self.output_dir / "amazon_login_error.png"
                            page.screenshot(path=str(screenshot_path))
                            print(f"Saved login error screenshot to {screenshot_path}")
                            
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
                            print("Could not verify login status. Aborting Amazon scraping.")
                            return
            except TimeoutError as e:
                print(f"Timeout error during Amazon scraping: {e}")
                print("The operation took too long to complete. This could be due to slow internet connection or website changes.")
                # Save a screenshot for debugging
                try:
                    screenshot_path = self.output_dir / "amazon_timeout_error.png"
                    page.screenshot(path=str(screenshot_path))
                    print(f"Saved timeout error screenshot to {screenshot_path}")
                except Exception as screenshot_error:
                    print(f"Error saving timeout screenshot: {screenshot_error}")
            except Exception as e:
                print(f"Error during Amazon scraping: {e}")
                print(f"Error type: {type(e).__name__}")
                print(f"Error details: {str(e)}")
                
                # Save a screenshot for debugging
                try:
                    screenshot_path = self.output_dir / "amazon_error.png"
                    page.screenshot(path=str(screenshot_path))
                    print(f"Saved error screenshot to {screenshot_path}")
                except Exception as screenshot_error:
                    print(f"Error saving error screenshot: {screenshot_error}")
            finally:
                print("\n=== Finished Amazon Scraping ===\n")
                if browser:
                    try:
                        browser.close()
                    except Exception as close_error:
                        print(f"Error closing browser: {close_error}")
            
            # Navigate to orders page
            print("Navigating to orders page...")
            page.goto('https://www.amazon.com/gp/your-account/order-history', timeout=self.timeout)
            page.wait_for_load_state('networkidle', timeout=self.timeout)

            # Setup download handler with a dynamic prefix
            self.current_order_number = "unknown"
            self.current_purchase_date = None
            
            def download_handler(download):
                # If we have a purchase date, use it for organizing files
                if self.current_purchase_date:
                    # Get the appropriate directory based on the purchase date
                    invoice_dir = self._get_invoice_directory("amazon", self.current_purchase_date)
                    
                    # Format date for filename
                    date_str = self.current_purchase_date.strftime("%m-%d")
                    
                    # Create filename with order number and date
                    filename = f"amazon_invoice_{self.current_order_number}_{date_str}.pdf"
                    
                    # Check if file already exists
                    file_path = invoice_dir / filename
                    if file_path.exists():
                        print(f"Invoice already exists: {file_path}")
                        # Skip download by returning a path (download.save_as won't be called)
                        return str(file_path)
                    
                    # Save the file
                    download.save_as(file_path)
                    print(f"Downloaded invoice to {file_path}")
                    return str(file_path)
                else:
                    # Fall back to date-based directory if no purchase date
                    downloads_dir = self.output_dir / "downloads"
                    downloads_dir.mkdir(exist_ok=True)
                    unknown_dir = downloads_dir / "unknown_date"
                    unknown_dir.mkdir(exist_ok=True)
                    
                    # Create filename with timestamp
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"amazon_invoice_{self.current_order_number}_{timestamp}.pdf"
                    
                    # Save the file
                    file_path = unknown_dir / filename
                    download.save_as(file_path)
                    print(f"Downloaded invoice to {file_path} (unknown purchase date)")
                    return str(file_path)
            
            # Set the download handler
            page.on('download', download_handler)

            print("Looking for orders and invoice links...")
            
            # Initialize pagination variables
            current_page = 1
            has_more_pages = True
            processed_orders = 0
            total_orders_processed = 0
            max_orders_to_process = self.max_orders if self.max_orders > 0 else float('inf')
            
            # Process all pages of orders
            while has_more_pages and total_orders_processed < max_orders_to_process:
                print(f"\n--- Processing Amazon orders page {current_page} ---\n")
                
                # Wait for the orders page to load completely
                try:
                    page.wait_for_load_state('domcontentloaded', timeout=20000)
                    page.wait_for_load_state('load', timeout=20000)
                    page.wait_for_timeout(2000)  # Additional wait for dynamic content
                except Exception as e:
                    print(f"Error waiting for orders page: {e}")
                    # Take a screenshot for debugging
                    screenshot_path = self.output_dir / f"amazon_orders_timeout_page{current_page}.png"
                    page.screenshot(path=str(screenshot_path))
                    print(f"Saved timeout screenshot to {screenshot_path}")
                
                # Find all order cards/rows with multiple selectors
                print("Looking for order cards/rows...")
                order_elements = []
                
                # Try multiple selectors to find order elements
                order_selectors = [
                    '.order-card',
                    '.js-order-card',
                    '.a-box-group',
                    '.order-info',
                    '.order',
                    '.your-orders-content .a-box',
                    '.a-section:has(.shipment)',
                    '.a-box:has(.a-color-secondary:has-text("Order placed"))',
                    '.yo-item-container',
                    '.a-box-group:has(.a-box-inner)'
                ]
                
                for selector in order_selectors:
                    try:
                        print(f"Trying selector: {selector}")
                        elements = page.query_selector_all(selector)
                        if elements and len(elements) > 0:
                            print(f"Found {len(elements)} order elements using selector: {selector}")
                            order_elements = elements
                            break
                    except Exception as e:
                        print(f"Error with selector '{selector}': {e}")
                
                # If no order elements found, try a JavaScript approach
                if not order_elements:
                    print("No specific order elements found, trying JavaScript approach...")
                    try:
                        # Use JavaScript to find potential order elements
                        js_result = page.evaluate("""() => {
                            // Look for elements that might be order containers
                            const potentialOrderElements = [
                                // Elements with order-related classes
                                ...Array.from(document.querySelectorAll('[class*="order"]')),
                                // Elements with shipment information
                                ...Array.from(document.querySelectorAll('.a-box-group, .a-box')),
                                // Elements with order dates
                                ...Array.from(document.querySelectorAll('div:has(.a-color-secondary:contains("Order placed"))')),
                            ];
                            
                            // Return the count of potential elements
                            return potentialOrderElements.length;
                        }""")
                        
                        print(f"JavaScript found {js_result} potential order elements")
                        
                        if js_result > 0:
                            # We found elements via JavaScript, set a flag to use JS for processing
                            print("Found order elements via JavaScript, will use them for processing")
                            has_js_elements = True
                        else:
                            has_js_elements = False
                            print("No order elements found via JavaScript either")
                    except Exception as e:
                        print(f"JavaScript approach failed: {e}")
                        has_js_elements = False
                else:
                    has_js_elements = False
                
                # Process orders found using standard selectors
                if order_elements:
                    print(f"Processing {len(order_elements)} orders on page {current_page}")
                    
                    for i, order_element in enumerate(order_elements):
                        try:
                            # Check if we've reached the maximum number of orders to process
                            if total_orders_processed >= max_orders_to_process:
                                print(f"Reached maximum number of orders to process ({max_orders_to_process})")
                                has_more_pages = False
                                break
                                
                            print(f"Processing order {i+1}/{len(order_elements)}")
                            
                            # Try to extract order number
                            order_number = "unknown"
                            try:
                                # Try multiple selectors for order number
                                order_number_selectors = [
                                    '.order-info',
                                    '.order-number',
                                    '.order-id',
                                    '.order-date-invoice-item',
                                    'span:has-text("Order #")',
                                    '.a-color-secondary:has-text("Order #")'
                                ]
                                
                                for selector in order_number_selectors:
                                    try:
                                        order_id_elem = order_element.query_selector(selector)
                                        if order_id_elem:
                                            order_text = order_id_elem.text_content()
                                            # Try to extract order number with regex
                                            match = re.search(r'Order\s+#?\s*(\w+-\w+-\w+|\w+)', order_text)
                                            if match:
                                                order_number = match.group(1)
                                                print(f"Found order number: {order_number}")
                                                break
                                    except Exception as e:
                                        print(f"Error extracting order number with selector {selector}: {e}")
                            except Exception as e:
                                print(f"Error extracting order number: {e}")
                            
                            # Set the current order number for the download handler
                            self.current_order_number = order_number
                            
                            # Try to find and extract purchase date
                            try:
                                # Look for date elements within this order
                                date_selectors = [
                                    '.order-date-invoice-item',
                                    '.a-color-secondary:has-text("Order placed")',
                                    '.order-date',
                                    'span:has-text("Order placed:")'
                                ]
                                
                                date_text = None
                                for selector in date_selectors:
                                    try:
                                        date_element = order_element.query_selector(selector)
                                        if date_element:
                                            date_text = date_element.text_content()
                                            print(f"Found date text: {date_text}")
                                            break
                                    except Exception as e:
                                        print(f"Error with date selector {selector}: {e}")
                                
                                if date_text:
                                    # Try to extract date with regex
                                    date_patterns = [
                                        r'Order placed:\s*(\w+\s+\d+,\s*\d{4})',
                                        r'Order placed\s*(\w+\s+\d+,\s*\d{4})',
                                        r'Ordered on\s*(\w+\s+\d+,\s*\d{4})',
                                        r'(\w+\s+\d+,\s*\d{4})',
                                        r'(\d{1,2}/\d{1,2}/\d{2,4})',
                                        r'(\d{1,2}-\d{1,2}-\d{2,4})'
                                    ]
                                    
                                    for pattern in date_patterns:
                                        match = re.search(pattern, date_text)
                                        if match:
                                            date_str = match.group(1)
                                            print(f"Extracted date string: {date_str}")
                                            
                                            # Try multiple date formats
                                            date_formats = [
                                                '%B %d, %Y',  # January 1, 2023
                                                '%b %d, %Y',  # Jan 1, 2023
                                                '%m/%d/%Y',   # 01/01/2023
                                                '%m/%d/%y',   # 01/01/23
                                                '%m-%d-%Y',   # 01-01-2023
                                                '%m-%d-%y'    # 01-01-23
                                            ]
                                            
                                            for date_format in date_formats:
                                                try:
                                                    self.current_purchase_date = datetime.strptime(date_str, date_format)
                                                    print(f"Parsed purchase date: {self.current_purchase_date}")
                                                    break
                                                except ValueError:
                                                    continue
                                            
                                            if self.current_purchase_date:
                                                break
                            except Exception as e:
                                print(f"Error extracting purchase date: {e}")
                                self.current_purchase_date = None
                            
                            # Look for invoice links within this order
                            invoice_links = []
                            invoice_selectors = [
                                'a:has-text("Invoice")',
                                'a:has-text("View invoice")',
                                'a:has-text("Download invoice")',
                                'a[href*="invoice"]',
                                '.a-link-normal:has-text("Invoice")',
                                'span:has-text("Invoice")'
                            ]
                            
                            for selector in invoice_selectors:
                                try:
                                    links = order_element.query_selector_all(selector)
                                    if links and len(links) > 0:
                                        print(f"Found {len(links)} invoice links using selector: {selector}")
                                        invoice_links = links
                                        break
                                except Exception as e:
                                    print(f"Error with invoice selector '{selector}': {e}")
                            
                            if invoice_links:
                                for j, link in enumerate(invoice_links):
                                    try:
                                        print(f"Clicking invoice link {j+1}/{len(invoice_links)} for order {order_number}")
                                        
                                        # Check if we need to handle an existing invoice
                                        if self.current_purchase_date:
                                            invoice_dir = self._get_invoice_directory("amazon", self.current_purchase_date)
                                            date_str = self.current_purchase_date.strftime("%m-%d")
                                            filename = f"amazon_invoice_{self.current_order_number}_{date_str}.pdf"
                                            file_path = invoice_dir / filename
                                            
                                            if file_path.exists():
                                                print(f"Invoice already exists: {file_path}")
                                                # Skip this invoice and continue with the next one
                                                continue
                                        
                                        # Click the link to download the invoice
                                        link.click()
                                        page.wait_for_timeout(3000)  # Wait for download to start
                                        processed_orders += 1
                                    except Exception as e:
                                        print(f"Error clicking invoice link: {e}")
                            else:
                                print(f"No invoice links found for order {order_number}")
                                
                                # Try to find "Order Details" or similar links
                                details_selectors = [
                                    'a:has-text("Order Details")',
                                    'a:has-text("View order details")',
                                    'a:has-text("View order")',
                                    'a[href*="order-details"]',
                                    '.a-link-normal:has-text("Details")'
                                ]
                                
                                details_link = None
                                for selector in details_selectors:
                                    try:
                                        link = order_element.query_selector(selector)
                                        if link:
                                            print(f"Found order details link using selector: {selector}")
                                            details_link = link
                                            break
                                    except Exception as e:
                                        print(f"Error with details selector '{selector}': {e}")
                                
                                if details_link:
                                    try:
                                        print(f"Clicking order details link for order {order_number}")
                                        
                                        # Open in a new tab to avoid losing our place on the orders page
                                        # First get the href attribute
                                        details_url = None
                                        try:
                                            details_url = details_link.get_attribute('href')
                                        except:
                                            # If we can't get the href, just click the link
                                            details_url = None
                                        
                                        if details_url and details_url.startswith('http'):
                                            # Open in a new page
                                            print(f"Opening details in new tab: {details_url}")
                                            details_page = context.new_page()
                                            details_page.goto(details_url, timeout=self.timeout)
                                            details_page.wait_for_load_state('domcontentloaded', timeout=self.timeout)
                                        else:
                                            # Click the link and navigate in the current page
                                            details_link.click()
                                            page.wait_for_load_state('domcontentloaded', timeout=self.timeout)
                                            details_page = page
                                        
                                        # Wait for page to load
                                        details_page.wait_for_timeout(2000)
                                        
                                        # Try to extract purchase date from the details page
                                        try:
                                            # Look for date elements on the details page
                                            details_date_selectors = [
                                                '.order-date-invoice-item',
                                                '.a-color-secondary:has-text("Order placed")',
                                                '.order-date',
                                                'span:has-text("Order placed:")',
                                                '.date-display'
                                            ]
                                            
                                            details_date_text = None
                                            for selector in details_date_selectors:
                                                try:
                                                    date_element = details_page.query_selector(selector)
                                                    if date_element:
                                                        details_date_text = date_element.text_content()
                                                        print(f"Found date text on details page: {details_date_text}")
                                                        break
                                                except Exception as e:
                                                    print(f"Error with date selector {selector} on details page: {e}")
                                            
                                            if details_date_text:
                                                # Try to extract date with regex
                                                date_patterns = [
                                                    r'Order placed:\s*(\w+\s+\d+,\s*\d{4})',
                                                    r'Order placed\s*(\w+\s+\d+,\s*\d{4})',
                                                    r'Ordered on\s*(\w+\s+\d+,\s*\d{4})',
                                                    r'(\w+\s+\d+,\s*\d{4})',
                                                    r'(\d{1,2}/\d{1,2}/\d{2,4})',
                                                    r'(\d{1,2}-\d{1,2}-\d{2,4})'
                                                ]
                                                
                                                for pattern in date_patterns:
                                                    match = re.search(pattern, details_date_text)
                                                    if match:
                                                        date_str = match.group(1)
                                                        print(f"Extracted date string from details page: {date_str}")
                                                        
                                                        # Try multiple date formats
                                                        date_formats = [
                                                            '%B %d, %Y',  # January 1, 2023
                                                            '%b %d, %Y',  # Jan 1, 2023
                                                            '%m/%d/%Y',   # 01/01/2023
                                                            '%m/%d/%y',   # 01/01/23
                                                            '%m-%d-%Y',   # 01-01-2023
                                                            '%m-%d-%y'    # 01-01-23
                                                        ]
                                                        
                                                        for date_format in date_formats:
                                                            try:
                                                                self.current_purchase_date = datetime.strptime(date_str, date_format)
                                                                print(f"Parsed purchase date from details page: {self.current_purchase_date}")
                                                                break
                                                            except ValueError:
                                                                continue
                                                        
                                                        if self.current_purchase_date:
                                                            break
                                    except Exception as e:
                                        print(f"Error extracting purchase date from details page: {e}")
                                        
                                        # Look for invoice links on the details page
                                        details_invoice_selectors = [
                                            'a:has-text("Invoice")',
                                            'a:has-text("View invoice")',
                                            'a:has-text("Download invoice")',
                                            'a[href*="invoice"]',
                                            '.a-link-normal:has-text("Invoice")'
                                        ]
                                        
                                        details_invoice_found = False
                                        for selector in details_invoice_selectors:
                                            try:
                                                links = details_page.query_selector_all(selector)
                                                if links and len(links) > 0:
                                                    print(f"Found {len(links)} invoice links on details page using selector: {selector}")
                                                    for link in links:
                                                        try:
                                                            print(f"Clicking invoice link on details page for order {order_number}")
                                                            
                                                            # Check if we need to handle an existing invoice
                                                            if self.current_purchase_date:
                                                                invoice_dir = self._get_invoice_directory("amazon", self.current_purchase_date)
                                                                date_str = self.current_purchase_date.strftime("%m-%d")
                                                                filename = f"amazon_invoice_{self.current_order_number}_{date_str}.pdf"
                                                                file_path = invoice_dir / filename
                                                                
                                                                if file_path.exists():
                                                                    print(f"Invoice already exists: {file_path}")
                                                                    # Skip this invoice and continue with the next one
                                                                    continue
                                                            
                                                            # Click the link to download the invoice
                                                            link.click()
                                                            details_page.wait_for_timeout(3000)  # Wait for download to start
                                                            processed_orders += 1
                                                            details_invoice_found = True
                                                        except Exception as e:
                                                            print(f"Error clicking invoice link on details page: {e}")
                                                    
                                                    if details_invoice_found:
                                                        break
                                            except Exception as e:
                                                print(f"Error with invoice selector '{selector}' on details page: {e}")
                                        
                                        # If we opened a new tab, close it
                                        if details_url and details_url.startswith('http'):
                                            try:
                                                details_page.close()
                                            except Exception as e:
                                                print(f"Error closing details page: {e}")
                                            
                                            # Make sure we're back on the orders page
                                            page.bring_to_front()
                                    except Exception as e:
                                        print(f"Error processing order details: {e}")
                                        
                                        # If we navigated away from the orders page, go back
                                        if "order-history" not in page.url:
                                            print("Navigating back to orders page...")
                                            page.goto('https://www.amazon.com/gp/your-account/order-history', timeout=self.timeout)
                                            page.wait_for_load_state('networkidle', timeout=self.timeout)
                            
                            # Increment the total orders processed counter
                            total_orders_processed += 1
                        except Exception as e:
                            print(f"Error processing order: {e}")
                # Process orders using JavaScript approach if needed
                elif has_js_elements:
                    print("Processing orders using JavaScript approach...")
                    try:
                        # Use JavaScript to process orders
                        js_processed = page.evaluate("""() => {
                            // Function to extract text content safely
                            function safeTextContent(element) {
                                return element ? element.textContent.trim() : '';
                            }
                            
                            // Find all potential order elements
                            const potentialOrderElements = [
                                ...Array.from(document.querySelectorAll('[class*="order"]')),
                                ...Array.from(document.querySelectorAll('.a-box-group, .a-box')),
                                ...Array.from(document.querySelectorAll('div:has(.a-color-secondary:contains("Order placed"))')),
                            ];
                            
                            // Find all invoice links
                            const invoiceLinks = Array.from(document.querySelectorAll('a[href*="invoice"], a:contains("Invoice"), a:contains("invoice")'));
                            
                            // Return the count of invoice links found
                            return invoiceLinks.length;
                        }""")
                        
                        print(f"JavaScript found and processed {js_processed} potential invoice links")
                        
                        if js_processed > 0:
                            processed_orders += js_processed
                        else:
                            print("No invoice links found via JavaScript")
                    except Exception as e:
                        print(f"JavaScript processing failed: {e}")
                else:
                    print("No order elements found on this page")
                
                # Check if we need to navigate to the next page
                if processed_orders == 0:
                    print("No orders processed on this page, might be at the end")
                
                # Look for next page button
                next_page_selectors = [
                    'a:has-text("Next Page")',
                    'a:has-text("Next")',
                    'a.a-pagination-next',
                    'li.a-last > a',
                    'a[href*="startIndex="]',
                    'a.a-link-normal[href*="orderFilter="]'
                ]
                
                next_page_found = False
                for selector in next_page_selectors:
                    try:
                        next_button = page.query_selector(selector)
                        if next_button:
                            print(f"Found next page button using selector: {selector}")
                            
                            # Check if the next button is disabled
                            is_disabled = False
                            try:
                                parent_element = next_button.evaluate('node => node.parentElement')
                                if parent_element:
                                    parent_class = parent_element.get_attribute('class') or ''
                                    if 'a-disabled' in parent_class:
                                        is_disabled = True
                            except:
                                pass
                            
                            if not is_disabled:
                                print("Clicking next page button...")
                                next_button.click()
                                page.wait_for_load_state('domcontentloaded', timeout=self.timeout)
                                page.wait_for_timeout(2000)  # Additional wait for dynamic content
                                current_page += 1
                                next_page_found = True
                                break
                            else:
                                print("Next page button is disabled, reached the last page")
                                has_more_pages = False
                    except Exception as e:
                        print(f"Error with next page selector '{selector}': {e}")
                
                if not next_page_found:
                    print("No next page button found, reached the last page")
                    has_more_pages = False
                
                # Safety check to prevent infinite loops
                if current_page > 20:  # Arbitrary limit
                    print("Reached page limit (20), stopping pagination")
                    has_more_pages = False
            
            print(f"\nFinished processing Amazon orders. Total orders processed: {total_orders_processed}")
            
        except TimeoutError as e:
            print(f"Timeout error during Amazon scraping: {e}")
            print("The operation took too long to complete. This could be due to slow internet connection or website changes.")
            # Save a screenshot for debugging
            try:
                screenshot_path = self.output_dir / "amazon_timeout_error.png"
                page.screenshot(path=str(screenshot_path))
                print(f"Saved timeout error screenshot to {screenshot_path}")
            except Exception as screenshot_error:
                print(f"Error saving timeout screenshot: {screenshot_error}")
        except Exception as e:
            print(f"Error during Amazon scraping: {e}")
            print(f"Error type: {type(e).__name__}")
            print(f"Error details: {str(e)}")
            
            # Save a screenshot for debugging
            try:
                screenshot_path = self.output_dir / "amazon_error.png"
                page.screenshot(path=str(screenshot_path))
                print(f"Saved error screenshot to {screenshot_path}")
            except Exception as screenshot_error:
                print(f"Error saving error screenshot: {screenshot_error}")
