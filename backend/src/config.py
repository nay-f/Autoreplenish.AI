import os
import json
import bcrypt
import boto3
from dotenv import load_dotenv

load_dotenv()


def _load_runtime_secret_values(secret_id: str) -> dict:
    """Load non-AWS application secrets from Secrets Manager when configured.

    Local development continues to use environment variables. Staging and
    production should set SECRETS_MANAGER_SECRET_ID and grant only the Lambda
    execution role read access to that secret.
    """
    if not secret_id:
        return {}
    try:
        client = boto3.client("secretsmanager", region_name=os.getenv("AWS_REGION", "us-east-1"))
        response = client.get_secret_value(SecretId=secret_id)
        value = response.get("SecretString", "{}")
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            raise ValueError("Secrets Manager value must be a JSON object")
        return parsed
    except Exception as exc:
        if os.getenv("ENVIRONMENT", "development").lower() in ("staging", "production"):
            raise RuntimeError("Unable to load application secrets from Secrets Manager") from exc
        return {}


_RUNTIME_SECRETS = _load_runtime_secret_values(os.getenv("SECRETS_MANAGER_SECRET_ID", ""))
_SAP_RUNTIME_SECRETS = _load_runtime_secret_values(
    os.getenv("SAP_SECRETS_MANAGER_SECRET_ID", "")
    if os.getenv("SAP_WRITE_ENABLED", "false").lower() == "true"
    else ""
)


def _setting(name: str, default: str = "") -> str:
    return os.getenv(name) or str(_RUNTIME_SECRETS.get(name, default))


def _sap_setting(name: str, default: str = "") -> str:
    return os.getenv(name) or str(_SAP_RUNTIME_SECRETS.get(name, default))

# AWS Configuration
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
SAP_WRITE_ENABLED = os.getenv("SAP_WRITE_ENABLED", "false").lower() == "true"

_DEFAULT_TABLE_BY_ENVIRONMENT = {
    "development": "AutoReplenish_DevTable",
    "staging": "AutoReplenish_StagingTable",
    "production": "AutoReplenish_ProductionTable",
}
DYNAMODB_TABLE = os.getenv(
    "DYNAMODB_TABLE", _DEFAULT_TABLE_BY_ENVIRONMENT.get(ENVIRONMENT, "AutoReplenish_DevTable")
)
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-3-5-sonnet-20241022-v2:0")

# Durable approval-to-SAP processing. Configure an SQS FIFO queue in staging/production.
APPROVAL_QUEUE_URL = os.getenv("APPROVAL_QUEUE_URL", "")
SQS_QUEUE_ENABLED = bool(APPROVAL_QUEUE_URL)


def _validate_environment_boundary() -> None:
    """Reject obvious cross-environment resource configuration mistakes."""
    forbidden = {
        "development": ("production", "staging"),
        "staging": ("production",),
        "production": ("development", "dev", "staging"),
    }.get(ENVIRONMENT, ())
    resource_values = (DYNAMODB_TABLE.lower(), APPROVAL_QUEUE_URL.lower())
    for marker in forbidden:
        if any(marker in value for value in resource_values):
            raise RuntimeError(
                f"Environment boundary violation: {ENVIRONMENT} resource references {marker}."
            )


_validate_environment_boundary()

# External Signal Credentials
OPENWEATHER_API_KEY = _setting("OPENWEATHER_API_KEY")

# Telegram Configuration
TELEGRAM_BOT_TOKEN = _setting("TELEGRAM_BOT_TOKEN")
TELEGRAM_DEFAULT_CHAT_ID = _setting("TELEGRAM_DEFAULT_CHAT_ID")
TELEGRAM_WEBHOOK_SECRET = _setting("TELEGRAM_WEBHOOK_SECRET")
TELEGRAM_REQUIRE_STORE_BINDING = os.getenv("TELEGRAM_REQUIRE_STORE_BINDING", "true").lower() == "true"
ENABLE_LEGACY_BACKGROUND_WORKERS = os.getenv("ENABLE_LEGACY_BACKGROUND_WORKERS", "false").lower() == "true"

# SAP BTP Credentials
SAP_TOKEN_URL = _sap_setting("SAP_TOKEN_URL")
SAP_CLIENT_ID = _sap_setting("SAP_CLIENT_ID")
SAP_CLIENT_SECRET = _sap_setting("SAP_CLIENT_SECRET")
SAP_AI_API_URL = _sap_setting("SAP_AI_API_URL")

# Security, JWT & CORS Configuration
JWT_SECRET_KEY = _setting("JWT_SECRET_KEY", "change-this-in-production-immediately")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "8"))

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

ADMIN_USERNAME = _setting("ADMIN_USERNAME", "admin")
_RAW_PASSWORD = _setting("ADMIN_PASSWORD", "admin123")
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

if ENVIRONMENT == "production":
    if JWT_SECRET_KEY == "change-this-in-production-immediately":
        raise RuntimeError("JWT_SECRET_KEY must be supplied in production.")
    if os.getenv("SAP_WRITE_ENABLED") is None:
        raise RuntimeError("SAP_WRITE_ENABLED must be set explicitly in production.")

if ENVIRONMENT in ("staging", "production") and not os.getenv("SECRETS_MANAGER_SECRET_ID"):
    raise RuntimeError("SECRETS_MANAGER_SECRET_ID must be supplied in staging and production.")

if ENVIRONMENT == "production" and SAP_WRITE_ENABLED and not os.getenv("SAP_SECRETS_MANAGER_SECRET_ID"):
    raise RuntimeError("SAP_SECRETS_MANAGER_SECRET_ID must be supplied when production SAP write is enabled.")
