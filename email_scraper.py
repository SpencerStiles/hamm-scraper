import imaplib
import email
import os
from email.header import decode_header
from pathlib import Path
from typing import List
import PyPDF2
from config import EmailConfig, CompanyConfig

class EmailScraper:
    def __init__(self, company_config: CompanyConfig):
        self.config = company_config
        self.email_config = company_config.email_config
        self.output_dir = Path(company_config.output_directory)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def connect(self):
        self.imap = imaplib.IMAP4_SSL(
            self.email_config.imap_server,
            self.email_config.imap_port
        )
        self.imap.login(self.email_config.email, self.email_config.password)

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
        self.connect()
        self.imap.select("INBOX")

        # Search for emails from the last X days
        date = (datetime.now() - timedelta(days=days_back)).strftime("%d-%b-%Y")
        _, messages = self.imap.search(None, f'(SINCE {date})')

        for msg_num in messages[0].split():
            _, msg_data = self.imap.fetch(msg_num, "(RFC822)")
            email_body = msg_data[0][1]
            email_message = email.message_from_bytes(email_body)
            
            # Get email date
            email_date = parsedate_to_datetime(email_message["date"])

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

        self.disconnect()

if __name__ == "__main__":
    # Example usage
    from datetime import datetime, timedelta
    from email.utils import parsedate_to_datetime
    
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
