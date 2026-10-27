import os
import bcrypt
from dotenv import load_dotenv

load_dotenv()

# AWS Configuration
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE", "AutoReplenish_CoreTable")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-3-5-sonnet-20241022-v2:0")

# External Signal Credentials
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_DEFAULT_CHAT_ID = os.getenv("TELEGRAM_DEFAULT_CHAT_ID", "")

# SAP BTP Credentials
SAP_TOKEN_URL = os.getenv("SAP_TOKEN_URL", "")
SAP_CLIENT_ID = os.getenv("SAP_CLIENT_ID", "")
SAP_CLIENT_SECRET = os.getenv("SAP_CLIENT_SECRET", "")
SAP_AI_API_URL = os.getenv("SAP_AI_API_URL", "")

# Security, JWT & CORS Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-this-in-production-immediately")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "8"))

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
_RAW_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
# Simpan dalam bentuk bcrypt hash di memori runtime
ADMIN_PASSWORD_HASH = bcrypt.hashpw(_RAW_PASSWORD.encode("utf-8"), bcrypt.gensalt())

# AI Governance & Versioning (Fase 3)
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v2.0-pareto-hybrid")
RULE_ENGINE_VERSION = os.getenv("RULE_ENGINE_VERSION", "v1.2-moq-guardrail")

# Batas pengali keamanan (AI tidak boleh merekomendasikan > 2.5x dari kebutuhan baseline normal)
AI_MAX_MULTIPLIER_CAP = float(os.getenv("AI_MAX_MULTIPLIER_CAP", "2.5"))
AI_MIN_MULTIPLIER_FLOOR = float(os.getenv("AI_MIN_MULTIPLIER_FLOOR", "0.3"))

# Kebijakan Confidence Threshold
CONFIDENCE_HIGH_THRESHOLD = 0.85
CONFIDENCE_MIN_ACCEPTABLE = 0.60