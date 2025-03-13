# Invoice Organizer

A scalable solution for automatically downloading and organizing invoices from both email and web portals (Walmart, Amazon) for multiple companies.

## Features

- Email invoice scraping using IMAP
- Web portal scraping for Walmart and Amazon
- Scalable configuration for multiple companies
- Organized file storage by company and date
- Automatic duplicate file handling
- Error handling and logging

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure your settings:
   - Copy `.env.example` to `.env`
   - Edit `.env` with your companies' credentials
   - For each company, you can configure:
     - Email settings (IMAP)
     - Walmart credentials
     - Amazon credentials

## Configuration

The `.env` file supports multiple companies. For each company, you can configure:

- Email credentials (optional)
- Walmart account credentials (optional)
- Amazon account credentials (optional)

To add more companies, simply:
1. Increment the `COMPANY_COUNT` in `.env`
2. Add the corresponding company configuration using the next number

## Usage

Run the script:
```bash
python main.py
```

The script will:
1. Process emails for each configured company
2. Download invoices from Walmart and Amazon accounts
3. Organize files into company-specific folders by date

## Output Structure

```
downloads/
├── Company1/
│   ├── 2025-03/
│   │   ├── email_invoice1.pdf
│   │   ├── walmart_invoice1.pdf
│   │   └── amazon_invoice1.pdf
│   └── 2025-04/
│       └── ...
└── Company2/
    └── ...
```

## Security Notes

- Store your `.env` file securely and never commit it to version control
- Use environment variables for sensitive credentials
- The script uses secure HTTPS/SSL connections for web scraping
