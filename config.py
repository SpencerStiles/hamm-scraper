from pydantic import BaseModel
from typing import List, Dict, Optional

class EmailConfig(BaseModel):
    email: str
    password: str
    imap_server: str
    imap_port: int = 993

class WebsiteCredentials(BaseModel):
    username: str
    password: str

class CompanyConfig(BaseModel):
    name: str
    email_config: Optional[EmailConfig] = None
    walmart_credentials: Optional[WebsiteCredentials] = None
    amazon_credentials: Optional[WebsiteCredentials] = None
    output_directory: str

class Config(BaseModel):
    companies: List[CompanyConfig]
    base_download_path: str = "./downloads"
