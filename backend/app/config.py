import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = "sqlite:///./app.db"
SECRET_KEY = "your_super_secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

