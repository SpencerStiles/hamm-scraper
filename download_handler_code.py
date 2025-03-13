# Replace your current _handle_download method with this improved version
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
