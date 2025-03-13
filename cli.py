import argparse
import os
from pathlib import Path
from dotenv import load_dotenv
from config import Config, CompanyConfig, EmailConfig, WebsiteCredentials
from email_scraper import EmailScraper
from web_scraper import WebScraper
from main import load_config, process_company

def setup_argparse():
    parser = argparse.ArgumentParser(description='Invoice Organizer CLI')
    
    # Main command options
    parser.add_argument('--list-companies', action='store_true', help='List all configured companies')
    parser.add_argument('--company', type=str, help='Process a specific company by name')
    parser.add_argument('--all', action='store_true', help='Process all companies')
    
    # Component options
    parser.add_argument('--email-only', action='store_true', help='Only process email scraping')
    parser.add_argument('--web-only', action='store_true', help='Only process web scraping')
    parser.add_argument('--walmart-only', action='store_true', help='Only process Walmart scraping')
    parser.add_argument('--amazon-only', action='store_true', help='Only process Amazon scraping')
    
    # Other options
    parser.add_argument('--days', type=int, default=30, help='Number of days back to search for emails (default: 30)')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode (no UI)')
    parser.add_argument('--persistent-browser', action='store_true', 
                        help='Use a persistent browser profile instead of a new session each time')
    parser.add_argument('--no-incognito', action='store_true',
                        help='Disable incognito mode for the browser')
    parser.add_argument('--timeout', type=int, default=30,
                        help='Timeout in seconds for web operations (default: 30)')
    parser.add_argument('--manual-timeout', type=int, default=60,
                        help='Timeout in seconds for manual authentication (default: 60)')
    parser.add_argument('--manual-mode', action='store_true', 
                        help='Wait for user confirmation after login (unlimited time for CAPTCHA/2FA)')
    parser.add_argument('--pure-manual', action='store_true', 
                        help='Skip automatic form filling and allow completely manual login')
    
    return parser

def list_companies(config):
    print("\nConfigured Companies:")
    print("=====================")
    
    if not config.companies:
        print("No companies configured. Please set up your .env file.")
        return
    
    for i, company in enumerate(config.companies, 1):
        print(f"{i}. {company.name}")
        print(f"   Output Directory: {company.output_directory}")
        
        if company.email_config:
            print(f"   Email: {company.email_config.email}")
        else:
            print("   Email: Not configured")
            
        if company.walmart_credentials:
            print(f"   Walmart: {company.walmart_credentials.username}")
        else:
            print("   Walmart: Not configured")
            
        if company.amazon_credentials:
            print(f"   Amazon: {company.amazon_credentials.username}")
        else:
            print("   Amazon: Not configured")
        
        print()

def process_company_with_options(company, args):
    """Process a company with the specified options"""
    print(f"\nProcessing company: {company.name}")
    
    # Create company output directory
    output_dir = Path(company.output_directory)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Email scraping
    if (not args.web_only) and (not args.walmart_only) and (not args.amazon_only):
        if company.email_config:
            print("Starting email scraping...")
            try:
                scraper = EmailScraper(company)
                scraper.process_emails(days_back=args.days)
            except Exception as e:
                print(f"Error during email scraping: {e}")
            print("Email scraping completed")
        else:
            print("Email scraping skipped - no email configuration provided")
    
    # Web scraping
    if (not args.email_only):
        print("Starting web scraping...")
        web_scraper = WebScraper(company, headless=args.headless, manual_mode=args.manual_mode, 
                                pure_manual=args.pure_manual, persistent_browser=args.persistent_browser,
                                incognito_mode=not args.no_incognito)
        
        # Set timeout values
        web_scraper.timeout = args.timeout * 1000  # Convert to milliseconds
        web_scraper.manual_timeout = args.manual_timeout * 1000  # Convert to milliseconds
        
        if (not args.amazon_only) and company.walmart_credentials:
            try:
                print("Processing Walmart invoices...")
                web_scraper.scrape_walmart()
            except Exception as e:
                print(f"Error during Walmart scraping: {e}")
            print("Walmart processing completed")
        else:
            if args.walmart_only:
                print("Walmart processing skipped - no credentials provided")
        
        if (not args.walmart_only) and company.amazon_credentials:
            try:
                print("Processing Amazon invoices...")
                web_scraper.scrape_amazon()
            except Exception as e:
                print(f"Error during Amazon scraping: {e}")
            print("Amazon processing completed")
        else:
            if args.amazon_only:
                print("Amazon processing skipped - no credentials provided")

def main():
    parser = setup_argparse()
    args = parser.parse_args()
    
    print("Loading configuration...")
    config = load_config()
    
    if not config.companies:
        print("No companies configured. Please set up your .env file.")
        return
    
    if args.list_companies:
        list_companies(config)
        return
    
    if args.company:
        # Find the company by name
        company = next((c for c in config.companies if c.name.lower() == args.company.lower()), None)
        if company:
            process_company_with_options(company, args)
        else:
            print(f"Company '{args.company}' not found. Use --list-companies to see available companies.")
    elif args.all:
        print(f"Found {len(config.companies)} companies to process")
        for company in config.companies:
            process_company_with_options(company, args)
    else:
        parser.print_help()
    
    print("\nAll processing completed!")

if __name__ == "__main__":
    main()
