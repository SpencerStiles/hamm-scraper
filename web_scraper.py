from playwright.sync_api import sync_playwright
import asyncio
from pathlib import Path
from datetime import datetime
from config import CompanyConfig, WebsiteCredentials

class WebScraper:
    def __init__(self, company_config: CompanyConfig):
        self.config = company_config
        self.output_dir = Path(company_config.output_directory)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _setup_browser(self, playwright):
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            accept_downloads=True,
            viewport={'width': 1920, 'height': 1080}
        )
        return browser, context

    def scrape_walmart(self):
        if not self.config.walmart_credentials:
            print(f"No Walmart credentials for {self.config.name}")
            return

        with sync_playwright() as playwright:
            browser, context = self._setup_browser(playwright)
            page = context.new_page()
            
            try:
                # Login to Walmart
                page.goto('https://www.walmart.com/account/login')
                page.fill('#email-input', self.config.walmart_credentials.username)
                page.fill('#password-input', self.config.walmart_credentials.password)
                page.click('#sign-in-form-submit-btn')
                page.wait_for_load_state('networkidle')

                # Navigate to orders page
                page.goto('https://www.walmart.com/account/orders')
                page.wait_for_load_state('networkidle')

                # Create date-based directory
                date_dir = self.output_dir / datetime.now().strftime("%Y-%m")
                date_dir.mkdir(exist_ok=True)

                # Setup download handler
                page.on('download', lambda download: download.save_as(
                    date_dir / f"walmart_invoice_{download.suggested_filename}"
                ))

                # Find and click invoice download buttons
                invoice_buttons = page.query_selector_all('button:has-text("Invoice")')
                for button in invoice_buttons:
                    button.click()
                    page.wait_for_timeout(1000)  # Wait for download to start

            finally:
                browser.close()

    def scrape_amazon(self):
        if not self.config.amazon_credentials:
            print(f"No Amazon credentials for {self.config.name}")
            return

        with sync_playwright() as playwright:
            browser, context = self._setup_browser(playwright)
            page = context.new_page()
            
            try:
                # Login to Amazon
                page.goto('https://www.amazon.com/signin')
                page.fill('#ap_email', self.config.amazon_credentials.username)
                page.click('#continue')
                page.fill('#ap_password', self.config.amazon_credentials.password)
                page.click('#signInSubmit')
                page.wait_for_load_state('networkidle')

                # Navigate to orders page
                page.goto('https://www.amazon.com/gp/your-account/order-history')
                page.wait_for_load_state('networkidle')

                # Create date-based directory
                date_dir = self.output_dir / datetime.now().strftime("%Y-%m")
                date_dir.mkdir(exist_ok=True)

                # Setup download handler
                page.on('download', lambda download: download.save_as(
                    date_dir / f"amazon_invoice_{download.suggested_filename}"
                ))

                # Find and click invoice links
                invoice_links = page.query_selector_all('a:has-text("Invoice")')
                for link in invoice_links:
                    link.click()
                    page.wait_for_timeout(1000)  # Wait for download to start

            finally:
                browser.close()

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
