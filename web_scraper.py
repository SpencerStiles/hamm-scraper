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
            # Create the target directory if it doesn't exist
            os.makedirs(target_dir, exist_ok=True)
            
            # Get suggested filename from the download
            suggested_name = download.suggested_filename
            print(f"Download started: {suggested_name}")
            
            # Clean up the filename
            clean_name = re.sub(r'[\\/*?:"<>|]', '_', suggested_name)
            if not clean_name:
                clean_name = f"{prefix}{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            elif not clean_name.startswith(prefix):
                clean_name = f"{prefix}{clean_name}"
            
            # Set the download path
            download_path = os.path.join(target_dir, clean_name)
            
            # Save the download
            download.save_as(download_path)
            print(f"Download completed: {download_path}")
            
            # For PDF files, verify the content
            if download_path.lower().endswith('.pdf'):
                self._verify_pdf_download(download_path)
                
            return download_path
        except Exception as e:
            print(f"Error handling download: {e}")
            return None
            
    def _verify_pdf_download(self, pdf_path):
        """Verify that the downloaded PDF file is valid and not empty."""
        try:
            # Check file size first
            file_size = os.path.getsize(pdf_path)
            print(f"Downloaded PDF size: {file_size} bytes")
            
            if file_size < 1000:  # Less than 1KB is suspicious for a PDF
                print(f"Warning: PDF file is very small ({file_size} bytes), might be empty or invalid")
                
            # Try to open the PDF with PyPDF2 if available
            try:
                import PyPDF2
                with open(pdf_path, 'rb') as pdf_file:
                    try:
                        pdf_reader = PyPDF2.PdfReader(pdf_file)
                        num_pages = len(pdf_reader.pages)
                        print(f"PDF verified: {num_pages} pages")
                        return num_pages > 0
                    except Exception as pdf_error:
                        print(f"PDF validation error: {pdf_error}")
                        return False
            except ImportError:
                print("PyPDF2 not available for PDF validation")
                return file_size > 1000  # Consider valid if size is reasonable
                
        except Exception as e:
            print(f"Error verifying PDF: {e}")
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
                    # If not on account page, go there first
                    elif "/account" not in current_url:
                        print("Navigating to account page first...")
                        page.goto('https://www.walmart.com/account', timeout=30000)
                        
                        # Wait for page to load with more reliable checks
                        page.wait_for_load_state('domcontentloaded', timeout=20000)
                        page.wait_for_load_state('load', timeout=20000)
                        
                        # Wait for account page elements
                        account_page_loaded = False
                        account_page_selectors = [
                            'text="Account Home"',
                            'text="Account"',
                            '[data-automation-id="account-home"]',
                            '[data-testid="account-home"]'
                        ]
                        
                        for selector in account_page_selectors:
                            try:
                                if page.wait_for_selector(selector, timeout=10000, state='visible'):
                                    print(f"Account page loaded (detected via {selector})")
                                    account_page_loaded = True
                                    break
                            except:
                                pass
                        
                        if not account_page_loaded:
                            print("No specific account page elements found, waiting longer")
                            page.wait_for_timeout(5000)
                    
                    # Variable to track navigation success
                    found_link = False
                    
                    # Check if we're already on the orders page after potential navigation
                    current_url = page.url
                    if '/orders' in current_url:
                        print("Successfully reached orders page")
                        found_link = True
                    
                    # Only proceed with link finding if we're not already on the orders page
                    if not found_link:
                        # Now look for and click on "Purchase History" or "Orders" link
                        print("Looking for Purchase History/Orders link...")
                        purchase_history_selectors = [
                            '[data-automation-id*="yourOrders"]',
                            '[data-automation-id*="yourOrders"]',
                            '[id="yourOrders"]',
                            '[id*="yourOrders"]',
                            '[class*="yourOrders"]'
                        ]
                        
                        for selector in purchase_history_selectors:
                            if found_link:
                                break  # Skip remaining selectors if we already found a link
                            try:
                                print(f"Trying selector: {selector}")
                                if page.is_visible(selector, timeout=5000):
                                    print(f"Found visible element with selector: {selector}")
                                    page.click(selector)
                                    print(f"Clicked on element with selector: {selector}")
                                    page.wait_for_load_state('networkidle', timeout=30000)
                                    page.wait_for_timeout(3000)
                                    
                                    # Check if we're now on the orders page
                                    current_url = page.url
                                    if '/orders' in current_url:
                                        found_link = True
                                        print("Successfully navigated to orders page using selector")
                                    else:
                                        print(f"Clicked selector but not on orders page. Current URL: {current_url}")
                            except Exception as e:
                                print(f"Error with selector '{selector}': {e}")
                        
                        # If we still can't find the link, try JavaScript approach
                        if not found_link:
                            print("Trying JavaScript approach to find and click the orders link...")
                            try:
                                # Try to find and click using JavaScript
                                js_result = page.evaluate('''
                                    () => {
                                        // Try various ways to find the orders link
                                        let element = null;
                                        
                                        // Try by ID, data attributes, or containing text
                                        const selectors = [
                                            document.querySelector('[data-testid="yourOrders"]'),
                                            document.querySelector('[id="yourOrders"]'),
                                            document.querySelector('[data-automation-id="yourOrders"]'),
                                            document.getElementById('yourOrders')
                                        ];
                                        
                                        // Find first valid element
                                        for (const el of selectors) {
                                            if (el) {
                                                // Check if it's an orders link
                                                const text = el.textContent.toLowerCase();
                                                const href = el.getAttribute('href') || '';
                                                
                                                if (
                                                    text.includes('order') || 
                                                    text.includes('purchase') || 
                                                    href.includes('order') || 
                                                    href.includes('purchase') ||
                                                    el.id.includes('order') ||
                                                    (el.getAttribute('data-testid') || '').includes('order')
                                                ) {
                                                    element = el;
                                                    break;
                                                }
                                            }
                                        }
                                        
                                        // If we found an element, click it
                                        if (element) {
                                            element.click();
                                            return true;
                                        }
                                        
                                        return false;
                                    }
                                ''')
                                
                                if js_result:
                                    print("Successfully found and clicked orders link using JavaScript")
                                    # Wait for navigation
                                    page.wait_for_load_state('networkidle', timeout=30000)
                                    page.wait_for_timeout(3000)
                                    
                                    # Check if we're now on the orders page
                                    current_url = page.url
                                    if '/orders' in current_url or '/purchase-history' in current_url:
                                        found_link = True
                                        print("Successfully navigated to orders page via JavaScript")
                                    else:
                                        print(f"JavaScript click didn't reach orders page. Current URL: {current_url}")
                                else:
                                    print("JavaScript approach did not find a suitable link")
                            except Exception as e:
                                print(f"Error with JavaScript approach: {e}")
                        
                        # If we still can't find the link, try direct navigation
                        if not found_link:
                            print("Could not find Purchase History/Orders link, trying direct navigation...")
                            try:
                                page.goto('https://www.walmart.com/orders', timeout=30000)
                                print("Direct navigation to orders page attempted")
                                page.wait_for_load_state('networkidle', timeout=30000)
                                page.wait_for_timeout(3000)
                                
                                # Check if we're on the orders page
                                current_url = page.url
                                print(f"Current URL after direct navigation: {current_url}")
                                if '/orders' in current_url or '/purchase-history' in current_url:
                                    print("Successfully navigated to orders page via direct URL")
                                    found_link = True
                                else:
                                    print("Direct navigation did not reach orders page")
                            except Exception as e:
                                print(f"Error during direct navigation: {e}")
                                # Take a screenshot for debugging
                                screenshot_path = self.output_dir / "walmart_navigation_error.png"
                                page.screenshot(path=str(screenshot_path))
                                print(f"Saved navigation error screenshot to {screenshot_path}")
                    
                    # If we still couldn't navigate to the orders page, try one more direct approach
                    if not found_link:
                        print("Trying one final direct navigation to the orders page...")
                        try:
                            page.goto('https://www.walmart.com/orders', timeout=30000)
                            page.wait_for_timeout(5000)
                            
                            current_url = page.url
                            if '/orders' in current_url:
                                print("Successfully navigated to orders page via purchase-history URL")
                                found_link = True
                            else:
                                print(f"Final navigation attempt failed. Current URL: {current_url}")
                                # Log error but continue with the process
                                print("Continuing with the current page despite navigation issues")
                                found_link = True  # Force continue without manual intervention
                        except Exception as e:
                            print(f"Error during final navigation attempt: {e}")
                            # Continue anyway
                            print("Continuing with the current page despite navigation error")
                            found_link = True  # Force continue without manual intervention
                    
                    # Take a screenshot for verification
                    screenshot_path = self.output_dir / "walmart_orders_page.png"
                    page.screenshot(path=str(screenshot_path))
                    print(f"Saved orders page screenshot to {screenshot_path}")
                    
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

                # Setup download handler
                page.on('download', lambda download: self._handle_download(download, date_dir, "walmart_invoice_"))
                
                # Wait for the orders page to load completely
                print("Waiting for orders page to load...")
                try:
                    page.wait_for_load_state('domcontentloaded', timeout=20000)
                    page.wait_for_load_state('load', timeout=20000)
                    
                    # Wait for specific elements that indicate the page has loaded
                    order_loaded = False
                    order_content_selectors = [
                        '[data-automation-id*="order-card"]',
                        '[data-testid*="order-card"]',
                        'text=Order #',
                        'text=Order Details',
                        '.order-details',
                        '#order-details'
                    ]
                    
                    for selector in order_content_selectors:
                        try:
                            if page.wait_for_selector(selector, timeout=15000, state='visible'):
                                print(f"Orders page loaded (detected via {selector})")
                                order_loaded = True
                                break
                        except Exception as e:
                            print(f"Selector {selector} not found: {e}")
                    
                    if not order_loaded:
                        # If no specific selectors found, wait a bit longer and continue anyway
                        print("No specific orders page elements found, waiting longer")
                        page.wait_for_timeout(5000)
                    
                    print("Orders page considered loaded")
                except Exception as e:
                    print(f"Error waiting for orders page: {e}")
                    # Take a screenshot for debugging
                    screenshot_path = self.output_dir / "walmart_orders_timeout.png"
                    page.screenshot(path=str(screenshot_path))
                    print(f"Saved timeout screenshot to {screenshot_path}")
                
                # Find all "View order details" buttons with increased timeout and debugging
                print("Looking for 'View order details' buttons...")
                view_details_buttons = []
                
                # Try multiple selectors with explicit timeout and error handling
                view_details_selectors = [
                    'a:has-text("View order details")',
                    'button:has-text("View order details")',
                    'a:has-text("Order details")',
                    'button:has-text("Order details")',
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
                
                # If no buttons found, try waiting longer and checking again
                if not view_details_buttons:
                    print("No buttons found initially, waiting longer and trying again...")
                    try:
                        page.wait_for_timeout(5000)  # Wait a bit longer
                        
                        # Try the selectors again
                        for selector in view_details_selectors:
                            try:
                                buttons = page.query_selector_all(selector)
                                if buttons:
                                    print(f"Found {len(buttons)} buttons after waiting using selector: {selector}")
                                    view_details_buttons = buttons
                                    break
                            except Exception as e:
                                print(f"Error with selector '{selector}' after waiting: {e}")
                    except Exception as e:
                        print(f"Error during second attempt to find buttons: {e}")
                
                if not view_details_buttons:
                    print("No order details buttons found. Taking a screenshot for debugging...")
                    screenshot_path = self.output_dir / "walmart_no_orders_found.png"
                    page.screenshot(path=str(screenshot_path))
                    print(f"Saved screenshot to {screenshot_path}")
                    
                    # Check the HTML content for debugging
                    print("Checking page content for debugging...")
                    page_content = page.content()
                    if "order details" in page_content.lower() or "view order" in page_content.lower():
                        print("Page content contains 'order details' or 'view order' text, but selectors failed to match")
                    else:
                        print("Page content does not contain expected order-related text")
                    
                    print("No order details found, continuing with next steps")
                else:
                    print(f"Found {len(view_details_buttons)} 'View order details' buttons")
                    
                    # Process each order
                    for i, button in enumerate(view_details_buttons):
                        try:
                            print(f"Processing order {i+1}/{len(view_details_buttons)}")
                            
                            # Click the "View order details" button
                            print(f"Clicking 'View order details' button for order {i+1}")
                            button.click()
                            
                            # Wait for the order details page to load with increased timeout
                            print("Waiting for order details page to load...")
                            try:
                                # Wait for multiple load states instead of just networkidle
                                page.wait_for_load_state('domcontentloaded', timeout=30000)
                                page.wait_for_load_state('load', timeout=30000)
                                
                                # Wait for specific elements that indicate the page has loaded
                                order_loaded = False
                                order_content_selectors = [
                                    '[data-automation-id*="order-details"]',
                                    '[data-testid*="order-details"]',
                                    'text=Order #',
                                    'text=Order Details',
                                    '.order-details',
                                    '#order-details'
                                ]
                                
                                for selector in order_content_selectors:
                                    try:
                                        if page.wait_for_selector(selector, timeout=15000, state='visible'):
                                            print(f"Order details page loaded (detected via {selector})")
                                            order_loaded = True
                                            break
                                    except Exception as sel_error:
                                        print(f"Selector {selector} not found: {sel_error}")
                                
                                if not order_loaded:
                                    # If no specific selectors found, wait a bit longer and continue anyway
                                    print("No specific order details elements found, waiting longer")
                                    page.wait_for_timeout(5000)
                                
                                print("Order details page considered loaded")
                            except Exception as e:
                                print(f"Error waiting for order details page: {e}")
                                # Take a screenshot for debugging
                                screenshot_path = self.output_dir / f"walmart_order_details_timeout_{i+1}.png"
                                page.screenshot(path=str(screenshot_path))
                                print(f"Saved timeout screenshot to {screenshot_path}")
                                
                                # Go back to orders page and continue with next order
                                print("Going back to orders page...")
                                try:
                                    page.goto('https://www.walmart.com/orders', timeout=30000)
                                    
                                    # Wait for page to load with more reliable checks
                                    page.wait_for_load_state('domcontentloaded', timeout=20000)
                                    page.wait_for_load_state('load', timeout=20000)
                                    
                                    # Re-query the buttons for next iteration
                                    if i < len(view_details_buttons) - 1:  # Only if there are more orders to process
                                        print("Re-querying 'View order details' buttons...")
                                        view_details_buttons = page.query_selector_all('a:has-text("View order details"), button:has-text("View order details")')
                                        if not view_details_buttons:
                                            print("Could not find 'View order details' buttons after timeout recovery")
                                    continue  # Skip to next order
                                except Exception as nav_error:
                                    print(f"Error navigating back to orders page after timeout: {nav_error}")
                                    continue  # Skip to next order
                            
                            # Get the order number for the filename
                            order_number = "unknown"
                            try:
                                # Try different selectors for order number
                                order_number_selectors = [
                                    'text=Order # >> span',
                                    '[data-automation-id*="order-number"]',
                                    'text=/Order #[0-9]+/',
                                    'text=/Order number: [0-9]+/'
                                ]
                                
                                for selector in order_number_selectors:
                                    order_element = page.query_selector(selector)
                                    if order_element:
                                        order_text = order_element.text_content()
                                        # Extract just the number
                                        import re
                                        match = re.search(r'(\d+)', order_text)
                                        if match:
                                            order_number = match.group(1)
                                            print(f"Found order number: {order_number}")
                                            break
                            except Exception as e:
                                print(f"Error getting order number: {e}")
                            
                            # Look for invoice/receipt buttons on the details page
                            print("Looking for invoice/receipt buttons on the details page...")
                            invoice_selectors = [
                                'button:has-text("Invoice")',
                                'a:has-text("Invoice")',
                                'button:has-text("Receipt")',
                                'a:has-text("Receipt")',
                                'button:has-text("Print invoice")',
                                'a:has-text("Print invoice")',
                                'button:has-text("Download invoice")',
                                'a:has-text("Download invoice")',
                                '[data-automation-id*="invoice"]',
                                '[data-automation-id*="receipt"]',
                                '[data-testid*="invoice"]',
                                '[data-testid*="receipt"]'
                            ]
                            
                            downloaded_invoices = 0
                            for selector in invoice_selectors:
                                try:
                                    invoice_buttons = page.query_selector_all(selector)
                                    if invoice_buttons:
                                        print(f"Found {len(invoice_buttons)} invoice buttons using selector: {selector}")
                                        for j, inv_button in enumerate(invoice_buttons):
                                            print(f"Clicking invoice button {j+1}/{len(invoice_buttons)}")
                                            
                                            # Set up download listener before clicking
                                            with page.expect_download(timeout=30000) as download_info:
                                                try:
                                                    # Click with options to ensure it works properly
                                                    inv_button.click(force=True, timeout=10000)
                                                    print("Invoice button clicked")
                                                    
                                                    # Wait a moment for any dialogs or popups
                                                    page.wait_for_timeout(2000)
                                                    
                                                    # Check if we need to handle a print dialog
                                                    try:
                                                        # Look for a "Save as PDF" or similar option in any dialog that appeared
                                                        save_pdf_button = page.query_selector('button:has-text("Save as PDF"), button:has-text("Save"), button:has-text("Download")')
                                                        if save_pdf_button:
                                                            print("Found Save as PDF button in dialog, clicking it...")
                                                            save_pdf_button.click(force=True)
                                                            page.wait_for_timeout(2000)
                                                    except Exception as dialog_error:
                                                        print(f"No dialog handling needed or error: {dialog_error}")
                                                    
                                                    try:
                                                        # Wait for download to start
                                                        download = download_info.value
                                                        print("Download started, waiting for completion...")
                                                        
                                                        # Handle the download
                                                        download_path = self._handle_download(download, date_dir, f"walmart_invoice_{order_number}_")
                                                        if download_path:
                                                            print(f"Invoice downloaded successfully: {download_path}")
                                                            # Verify the PDF is valid
                                                            if self._verify_pdf_download(download_path):
                                                                downloaded_invoices += 1
                                                            else:
                                                                print("Downloaded PDF appears to be invalid or empty")
                                                        else:
                                                            print("Failed to download invoice")
                                                    except Exception as download_error:
                                                        print(f"Download error: {download_error}")
                                                        
                                                except Exception as click_error:
                                                    print(f"Error clicking invoice button: {click_error}")
                                                    
                                                    # Try an alternative approach - JavaScript click
                                                    try:
                                                        print("Trying JavaScript click...")
                                                        page.evaluate("button => button.click()", inv_button)
                                                        page.wait_for_timeout(5000)
                                                        print("JavaScript click executed")
                                                    except Exception as js_error:
                                                        print(f"JavaScript click failed: {js_error}")
                                except Exception as e:
                                    print(f"Error with invoice selector '{selector}': {e}")
                            
                            # If no invoices were downloaded, try using page.pdf() as a fallback
                            if downloaded_invoices == 0:
                                print("No invoices downloaded via buttons, using page.pdf() as fallback...")
                                pdf_path = date_dir / f"walmart_invoice_{order_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                                
                                try:
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
                                print("Attempting to return to orders page after error...")
                                # First try using the back button if available
                                back_button = page.query_selector('a:has-text("Back to orders"), button:has-text("Back to orders")')
                                if back_button:
                                    print("Found 'Back to orders' button, clicking it...")
                                    back_button.click()
                                    
                                    # Wait for page to load with more reliable checks
                                    page.wait_for_load_state('domcontentloaded', timeout=20000)
                                    page.wait_for_load_state('load', timeout=20000)
                                    
                                    # Wait for orders page elements
                                    orders_page_loaded = False
                                    orders_page_selectors = [
                                        'text="Order History"',
                                        'text="Your Orders"',
                                        '[data-automation-id*="order-card"]',
                                        '[data-testid*="order-card"]'
                                    ]
                                    
                                    for selector in orders_page_selectors:
                                        try:
                                            if page.wait_for_selector(selector, timeout=10000, state='visible'):
                                                print(f"Orders page loaded (detected via {selector})")
                                                orders_page_loaded = True
                                                break
                                        except:
                                            pass
                                    
                                    if not orders_page_loaded:
                                        print("No specific orders page elements found, waiting longer")
                                        page.wait_for_timeout(5000)
                                else:
                                    # If no back button, navigate directly to orders page
                                    print("No back button found, navigating directly to orders page...")
                                    page.goto('https://www.walmart.com/orders', timeout=45000)
                                    page.wait_for_load_state('domcontentloaded', timeout=20000)
                                    page.wait_for_load_state('load', timeout=20000)
                                    
                                    # Wait for orders page elements
                                    orders_page_loaded = False
                                    orders_page_selectors = [
                                        'text="Order History"',
                                        'text="Your Orders"',
                                        '[data-automation-id*="order-card"]',
                                        '[data-testid*="order-card"]'
                                    ]
                                    
                                    for selector in orders_page_selectors:
                                        try:
                                            if page.wait_for_selector(selector, timeout=10000, state='visible'):
                                                print(f"Orders page loaded (detected via {selector})")
                                                orders_page_loaded = True
                                                break
                                        except:
                                            pass
                                    
                                    if not orders_page_loaded:
                                        print("No specific orders page elements found, waiting longer")
                                        page.wait_for_timeout(5000)
                                
                                # Verify we're on the orders page
                                current_url = page.url
                                if '/orders' in current_url or '/purchase-history' in current_url:
                                    print("Successfully returned to orders page")
                                else:
                                    print(f"Warning: Not on orders page after navigation. Current URL: {current_url}")
                                
                                # Re-query the buttons as the page has been reloaded
                                if i < len(view_details_buttons) - 1:  # Only if there are more orders to process
                                    print("Re-querying 'View order details' buttons...")
                                    view_details_buttons = page.query_selector_all('a:has-text("View order details"), button:has-text("View order details")')
                                    if not view_details_buttons:
                                        print("Could not find 'View order details' buttons after returning to orders page")
                            except Exception as e:
                                print(f"Error during recovery navigation: {e}")
                                # Last resort - try direct navigation with longer timeout
                                try:
                                    print("Attempting final recovery navigation...")
                                    page.goto('https://www.walmart.com/orders', timeout=60000)
                                    page.wait_for_timeout(5000)
                                except Exception as final_error:
                                    print(f"Final recovery navigation failed: {final_error}")
                        except Exception as e:
                            print(f"Error processing order {i+1}: {e}")
                            screenshot_path = self.output_dir / f"walmart_order_processing_error_{i+1}.png"
                            page.screenshot(path=str(screenshot_path))
                            print(f"Saved error screenshot to {screenshot_path}")
                            
                            # Try to go back to orders page to continue with next order
                            try:
                                print("Attempting to return to orders page after error...")
                                # First try using the back button if available
                                back_button = page.query_selector('a:has-text("Back to orders"), button:has-text("Back to orders")')
                                if back_button:
                                    print("Found 'Back to orders' button, clicking it...")
                                    back_button.click()
                                    page.wait_for_load_state('domcontentloaded', timeout=20000)
                                    page.wait_for_load_state('load', timeout=20000)
                                    page.wait_for_timeout(3000)
                                else:
                                    # If no back button, navigate directly to orders page
                                    print("No back button found, navigating directly to orders page...")
                                    page.goto('https://www.walmart.com/orders', timeout=45000)
                                    page.wait_for_load_state('domcontentloaded', timeout=20000)
                                    page.wait_for_load_state('load', timeout=20000)
                                    page.wait_for_timeout(3000)
                                
                                # Verify we're on the orders page
                                current_url = page.url
                                if '/orders' in current_url:
                                    print("Successfully returned to orders page")
                                else:
                                    print(f"Warning: Not on orders page after navigation. Current URL: {current_url}")
                                
                                # Re-query the buttons for next iteration
                                if i < len(view_details_buttons) - 1:  # Only if there are more orders to process
                                    print("Re-querying 'View order details' buttons...")
                                    view_details_buttons = page.query_selector_all('a:has-text("View order details"), button:has-text("View order details")')
                                    if not view_details_buttons:
                                        print("Could not find 'View order details' buttons after returning to orders page")
                            except Exception as nav_error:
                                print(f"Error during recovery navigation: {nav_error}")
                                # Last resort - try direct navigation with longer timeout
                                try:
                                    print("Attempting final recovery navigation...")
                                    page.goto('https://www.walmart.com/orders', timeout=60000)
                                    page.wait_for_timeout(5000)
                                except Exception as final_error:
                                    print(f"Final recovery navigation failed: {final_error}")
                    
                    print("Finished processing all orders")
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
