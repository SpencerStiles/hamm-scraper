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

You can run the script in two ways:

### 1. Basic Usage

```bash
python main.py
```

This will process all companies configured in your `.env` file, handling both email and web scraping.

### 2. Advanced Usage with CLI

For more control, use the CLI interface:

```bash
python cli.py [options]
```

#### CLI Options:

- `--list-companies`: List all configured companies
- `--company NAME`: Process a specific company by name
- `--all`: Process all companies
- `--email-only`: Only process email scraping
- `--web-only`: Only process web scraping
- `--walmart-only`: Only process Walmart scraping
- `--amazon-only`: Only process Amazon scraping
- `--days N`: Number of days back to search for emails (default: 30)
- `--headless`: Run browser in headless mode (no UI)
- `--timeout N`: Timeout in seconds for web operations (default: 30)
- `--manual-timeout N`: Timeout in seconds for manual authentication (default: 60)
- `--manual-mode`: Wait for user confirmation after login (unlimited time for CAPTCHA/2FA)
- `--pure-manual`: Skip automatic form filling and allow completely manual login.
- `--persistent-browser`: Use a persistent browser profile to reduce CAPTCHA frequency and login issues.

#### Examples:

List all configured companies:
```bash
python cli.py --list-companies
```

Process only email for a specific company:
```bash
python cli.py --company MyCompany1 --email-only
```

Process only Walmart scraping for all companies in headless mode:
```bash
python cli.py --all --walmart-only --headless
```

Process everything for a company:
```bash
python cli.py --company MyCompany1
```

Process only emails:
```bash
python cli.py --company MyCompany1 --email-only
```

Process only Walmart with manual verification:
```bash
python cli.py --company MyCompany1 --walmart-only --manual-mode
```

Use pure manual mode for difficult login scenarios:
```bash
python cli.py --company MyCompany1 --walmart-only --pure-manual
```

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

## Gmail Security Note

For Gmail accounts, you need to use an App Password instead of your regular password:

1. Go to https://myaccount.google.com/apppasswords
2. Sign in with your Google account
3. Select 'Mail' as the app and give it a name (e.g., 'Invoice Organizer')
4. Click 'Generate'
5. Copy the 16-character password
6. Update your `.env` file with this password

## Web Scraping Security Notes

When running web scraping for the first time:

1. The script will open browser windows to log into your accounts
2. You may need to complete CAPTCHA or 2FA verification manually
3. After successful login, the script will navigate to the invoice pages
4. If no invoices are found, screenshots will be saved for debugging

### Handling Verification Challenges

#### Walmart Verification
When logging into Walmart, you may encounter a "hold button" verification:
1. Press and hold the button as instructed
2. If nothing happens after holding the button:
   - Click "Try another verification method" if available
   - Choose "Send code to email" or "Send code to phone"
   - Enter the code you receive
   - Complete the verification

#### Amazon Verification
When logging into Amazon, you may encounter various verification challenges:
1. Complete any CAPTCHA puzzles in the browser
2. If prompted for a verification code, check your email or phone
3. Enter the code you receive
4. If you see "unusual activity" warnings, approve the login

#### Troubleshooting Login Issues

If you're experiencing persistent login issues with Walmart or Amazon:

1. **Use Persistent Browser Mode**: 
   ```bash
   python cli.py --company MyCompany1 --persistent-browser
   ```
   This creates a persistent browser profile that makes the browser appear more like a regular user's browser, which can reduce CAPTCHA frequency and login issues.

2. **Use Pure Manual Mode**:
   ```bash
   python cli.py --company MyCompany1 --pure-manual --persistent-browser
   ```
   This gives you complete control over the login process, allowing you to navigate and log in manually.

3. **Clear Browser Data**:
   If you're still having issues, try removing the browser profile:
   ```bash
   # On Windows
   rmdir /s /q browser_data
   
   # On macOS/Linux
   rm -rf browser_data
   ```
   Then run the script again with the persistent browser option.

### Session Persistence

The script now supports session persistence for web scraping:

1. After you manually log in once, your session will be saved to the `sessions` directory
2. On subsequent runs, the script will attempt to reuse your saved session
3. This means you should only need to complete CAPTCHA/2FA once, not every time
4. If a session expires, you'll be prompted to log in manually again

To clear saved sessions and force a new login, delete the files in the `sessions` directory.
