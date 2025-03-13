import os
from pathlib import Path
from dotenv import load_dotenv
from config import Config, CompanyConfig, EmailConfig, WebsiteCredentials
from email_scraper import EmailScraper
from web_scraper import WebScraper

def load_config() -> Config:
    """Load configuration from environment variables"""
    load_dotenv()
    
    companies = []
    company_count = int(os.getenv('COMPANY_COUNT', '0'))
    
    for i in range(1, company_count + 1):
        prefix = f'COMPANY_{i}_'
        
        # Only create email config if credentials are provided
        email_config = None
        if os.getenv(f'{prefix}EMAIL'):
            email_config = EmailConfig(
                email=os.getenv(f'{prefix}EMAIL'),
                password=os.getenv(f'{prefix}EMAIL_PASSWORD'),
                imap_server=os.getenv(f'{prefix}IMAP_SERVER', 'imap.gmail.com'),
                imap_port=int(os.getenv(f'{prefix}IMAP_PORT', '993'))
            )
        
        # Only create website credentials if provided
        walmart_creds = None
        if os.getenv(f'{prefix}WALMART_USERNAME'):
            walmart_creds = WebsiteCredentials(
                username=os.getenv(f'{prefix}WALMART_USERNAME'),
                password=os.getenv(f'{prefix}WALMART_PASSWORD')
            )
            
        amazon_creds = None
        if os.getenv(f'{prefix}AMAZON_USERNAME'):
            amazon_creds = WebsiteCredentials(
                username=os.getenv(f'{prefix}AMAZON_USERNAME'),
                password=os.getenv(f'{prefix}AMAZON_PASSWORD')
            )
        
        company = CompanyConfig(
            name=os.getenv(f'{prefix}NAME', f'Company_{i}'),
            email_config=email_config,
            walmart_credentials=walmart_creds,
            amazon_credentials=amazon_creds,
            output_directory=os.path.join(
                os.getenv('BASE_DOWNLOAD_PATH', './downloads'),
                os.getenv(f'{prefix}NAME', f'Company_{i}')
            )
        )
        companies.append(company)
    
    return Config(
        companies=companies,
        base_download_path=os.getenv('BASE_DOWNLOAD_PATH', './downloads')
    )

def process_company(company: CompanyConfig):
    """Process both email and web scraping for a single company"""
    print(f"\nProcessing company: {company.name}")
    
    # Email scraping
    if company.email_config:
        print("Starting email scraping...")
        try:
            scraper = EmailScraper(company)
            scraper.process_emails()
            print("Email scraping completed")
        except Exception as e:
            print(f"Error during email scraping: {e}")
    
    # Web scraping
    print("Starting web scraping...")
    web_scraper = WebScraper(company)
    
    if company.walmart_credentials:
        try:
            print("Processing Walmart invoices...")
            web_scraper.scrape_walmart()
            print("Walmart processing completed")
        except Exception as e:
            print(f"Error during Walmart scraping: {e}")
    
    if company.amazon_credentials:
        try:
            print("Processing Amazon invoices...")
            web_scraper.scrape_amazon()
            print("Amazon processing completed")
        except Exception as e:
            print(f"Error during Amazon scraping: {e}")

def main():
    print("Loading configuration...")
    config = load_config()
    
    if not config.companies:
        print("No companies configured. Please set up your .env file.")
        return
    
    print(f"Found {len(config.companies)} companies to process")
    
    for company in config.companies:
        process_company(company)
    
    print("\nAll processing completed!")

if __name__ == "__main__":
    main()
