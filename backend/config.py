import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL        = os.getenv("FORGE_BASE_URL", "http://localhost:8080")
API_KEY         = os.getenv("FORGE_API_KEY",  "sk-no-key")
MODEL_NAME      = os.getenv("FORGE_MODEL_NAME", "local-model")
DB_PATH         = os.getenv("FORGE_DB_PATH",  "forge.db")

