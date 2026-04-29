import os
from pathlib import Path

from dotenv import load_dotenv


APP_ROOT = Path(__file__).resolve().parent
REPO_ROOT = APP_ROOT.parents[1]
DATA_DIR = APP_ROOT / "data"
LOG_DIR = APP_ROOT / "logs"
QUEUE_DIR = DATA_DIR / "queue"
CHROMA_DIR = DATA_DIR / "chroma"
MIND_VAULT_DIR = DATA_DIR / "mind_vault"

for path in (DATA_DIR, LOG_DIR, QUEUE_DIR, CHROMA_DIR, MIND_VAULT_DIR):
    path.mkdir(parents=True, exist_ok=True)

load_dotenv(APP_ROOT / ".env")
load_dotenv(REPO_ROOT / ".env")

# Shared system roots
BLACKBOOK_APP_PATH = Path(os.getenv("BLACKBOOK_APP_PATH", REPO_ROOT / "apps" / "blackbook"))
MARIDIAN_APP_PATH = Path(os.getenv("MARIDIAN_APP_PATH", REPO_ROOT / "apps" / "maridian"))
OLYMPUS_APP_PATH = Path(os.getenv("OLYMPUS_APP_PATH", REPO_ROOT / "apps" / "olympus"))

# System connections
BLACK_BOOK_DB_URL = os.getenv("BLACK_BOOK_DB_URL") or os.getenv("DATABASE_URL")
BLACKBOOK_DB_PATH = str(Path(os.getenv("BLACKBOOK_DB_PATH", DATA_DIR / "blackbook.db")))
MERIDIAN_VAULT_PATH = os.getenv("MERIDIAN_VAULT_PATH", str(MARIDIAN_APP_PATH))
MERIDIAN_STATE_PATH = os.getenv("MERIDIAN_STATE_PATH", str(MARIDIAN_APP_PATH / "vault_state.json"))
OLYMPUS_API_URL = os.getenv("OLYMPUS_API_URL", "http://127.0.0.1:8002")
OLYMPUS_STATUS_PATH = os.getenv("OLYMPUS_STATUS_PATH")  # legacy Apex JSON drop, optional
APOLLO_MIND_VAULT_PATH = os.getenv("APOLLO_MIND_VAULT_PATH", str(MIND_VAULT_DIR))

# Apollo internals
APOLLO_DB_PATH = str(Path(os.getenv("APOLLO_DB_PATH", DATA_DIR / "apollo.db")))
CHROMA_PATH = str(Path(os.getenv("CHROMA_PATH", CHROMA_DIR)))
AUDIT_LOG_PATH = str(Path(os.getenv("AUDIT_LOG_PATH", LOG_DIR / "apollo_audit.log")))
QUEUE_PATH = str(Path(os.getenv("QUEUE_PATH", QUEUE_DIR)))

# Channels
WHATSAPP_BRIDGE_PORT = int(os.getenv("WHATSAPP_BRIDGE_PORT", "3001"))
BRIEF_DELIVERY_TIME = os.getenv("BRIEF_DELIVERY_TIME", "07:00")

# API keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# LLM settings
PRIMARY_MODEL = os.getenv("PRIMARY_MODEL", "claude-opus-4-6")
FAST_MODEL = os.getenv("FAST_MODEL", "claude-haiku-4-5-20251001")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1024"))

# Pantheon runtime
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
PANTHEON_MODEL = os.getenv("PANTHEON_MODEL", "llama3.2")
PANTHEON_PRIMARY_PROVIDER = os.getenv("PANTHEON_PRIMARY_PROVIDER", "anthropic")
ANTHROPIC_TIMEOUT = float(os.getenv("ANTHROPIC_TIMEOUT", "45"))
