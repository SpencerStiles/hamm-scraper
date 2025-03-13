import imaplib
import email
import os
from email.header import decode_header
from pathlib import Path
from typing import List
import PyPDF2
from config import EmailConfig, CompanyConfig
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

class EmailScraper:
    def __init__(self, company_config: CompanyConfig):
        self.config = company_config
        self.email_config = company_config.email_config
        self.output_dir = Path(company_config.output_directory)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def connect(self):
        """
        Connect to the IMAP server with proper error handling for Gmail's security requirements
        """
        try:
            self.imap = imaplib.IMAP4_SSL(
                self.email_config.imap_server,
                self.email_config.imap_port
            )
            self.imap.login(self.email_config.email, self.email_config.password)
            print(f"Successfully connected to {self.email_config.imap_server} for {self.config.name}")
            return True
        except imaplib.IMAP4.error as e:
            if "Application-specific password required" in str(e):
                print("\nERROR: Gmail requires an app-specific password for this application.")
                print("Please follow these steps:")
                print("1. Go to https://myaccount.google.com/apppasswords")
                print("2. Sign in with your Google account")
                print("3. Select 'Mail' as the app and give it a name (e.g., 'Invoice Organizer')")
                print("4. Click 'Generate'")
                print("5. Copy the 16-character password")
                print("6. Update your .env file with this password instead of your regular password")
                print("For more information, visit: https://support.google.com/accounts/answer/185833")
            else:
                print(f"IMAP connection error: {e}")
            return False

    def disconnect(self):
        try:
            self.imap.close()
            self.imap.logout()
        except:
            pass

    def _save_attachment(self, part, email_date):
        if part.get_filename():
            filename = decode_header(part.get_filename())[0][0]
            if isinstance(filename, bytes):
                filename = filename.decode()
            
            # Create date-based subdirectory
            date_dir = self.output_dir / email_date.strftime("%Y-%m")
            date_dir.mkdir(exist_ok=True)
            
            filepath = date_dir / filename
            
            # Don't overwrite existing files
            if filepath.exists():
                base = filepath.stem
                ext = filepath.suffix
                counter = 1
                while filepath.exists():
                    filepath = date_dir / f"{base}_{counter}{ext}"
                    counter += 1

            with open(filepath, "wb") as f:
                f.write(part.get_payload(decode=True))
            return str(filepath)
        return None

    def process_emails(self, days_back: int = 30):
        """
        Process emails from the last X days
        """
        if not self.connect():
            return
            
        try:
            self.imap.select("INBOX")

            # Search for emails from the last X days
            date = (datetime.now() - timedelta(days=days_back)).strftime("%d-%b-%Y")
            _, messages = self.imap.search(None, f'(SINCE {date})')
            
            message_count = len(messages[0].split())
            print(f"Found {message_count} emails to process")
            
            if message_count == 0:
                print("No emails found in the specified date range")
                return

            for msg_num in messages[0].split():
                _, msg_data = self.imap.fetch(msg_num, "(RFC822)")
                email_body = msg_data[0][1]
                email_message = email.message_from_bytes(email_body)
                
                # Get email date
                email_date = parsedate_to_datetime(email_message["date"])
                subject = email_message.get("Subject", "No Subject")
                
                print(f"Processing email: {subject}")

                # Process attachments
                if email_message.is_multipart():
                    for part in email_message.walk():
                        if part.get_content_maintype() == "multipart":
                            continue
                        if part.get("Content-Disposition") is None:
                            continue
                        
                        saved_path = self._save_attachment(part, email_date)
                        if saved_path:
                            print(f"Saved attachment: {saved_path}")

            print(f"Email processing completed for {self.config.name}")
        except Exception as e:
            print(f"Error processing emails: {e}")
        finally:
            self.disconnect()

if __name__ == "__main__":
    # Example usage
    config = CompanyConfig(
        name="TestCompany",
        email_config=EmailConfig(
            email="test@example.com",
            password="password",
            imap_server="imap.gmail.com"
        ),
        output_directory="./downloads/TestCompany"
    )
    
    scraper = EmailScraper(config)
    scraper.process_emails()
