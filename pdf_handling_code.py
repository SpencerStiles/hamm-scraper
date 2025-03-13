# Add this method to your WebScraper class
def _verify_pdf_download(self, pdf_path):
    """Verify that the downloaded PDF file is valid and not empty."""
    try:
        # Check file size first
        file_size = os.path.getsize(pdf_path)
        print(f"Downloaded PDF size: {file_size} bytes")
        
        if file_size < 1000:  # Less than 1KB is suspicious for a PDF
            print(f"Warning: PDF file is very small ({file_size} bytes), might be empty or invalid")
            
        # Try to open the PDF with PyPDF2
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

# Replace the invoice button clicking section with this improved code
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
