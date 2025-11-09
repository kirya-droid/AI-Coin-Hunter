
from pathlib import Path
from dotenv import load_dotenv

def load_env():
    # Load .env from project root if present
    root = Path(__file__).resolve().parents[2]
    env_file = root / ".env"
    load_dotenv(env_file, override=False)
