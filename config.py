import os
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://checkocr:%s@192.168.0.250:3307/checkocr" %
                         quote_plus('Fez@14&Oasis'))
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
TESSERACT_CMD = os.getenv("TESSERACT_CMD")
