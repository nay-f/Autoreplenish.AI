"""Configuration & Environment Settings for AutoReplenish.ai.

All credentials are resolved lazily at call time (never at import time) so that
the module can be imported inside test runners without AWS credentials present.
Values are sourced, in priority order:
    1. Lambda environment variables (see infra/lambda.tf)
    2. AWS Secrets Manager (fetched by the owning service, cached per warm container)
    3. Explicit defaults for non-secret operational constants
"""

import os
import logging
from typing import Dict

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("AutoReplenish")

# AWS and Environment Constants
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
AWS_REGION = os.environ.get("AWS_REGION", "ap-southeast-1")
DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE", f"autoreplenish-main-{ENVIRONMENT}")
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0")

# Secret Names (Secrets Manager ARNs are created in infra/secrets.tf)
WEATHER_SECRET_NAME = os.environ.get("WEATHER_SECRET_NAME", f"autoreplenish/weather-credentials-{ENVIRONMENT}")
TELEGRAM_SECRET_NAME = os.environ.get("TELEGRAM_SECRET_NAME", f"autoreplenish/telegram-credentials-{ENVIRONMENT}")
SAP_SECRET_NAME = os.environ.get("SAP_SECRET_NAME", f"autoreplenish/sap-credentials-{ENVIRONMENT}")
SAP_PR_QUEUE_URL = os.environ.get("SAP_PR_QUEUE_URL", "")

# -------------------------------------------------------------
# External Signal: OpenWeatherMap (PRD Section 14.3)
# -------------------------------------------------------------
OPENWEATHERMAP_BASE_URL = os.environ.get(
    "OPENWEATHERMAP_BASE_URL", "https://api.openweathermap.org/data/2.5"
)
# Generic fallback coordinates (Jakarta Pusat), used by WeatherService ONLY when a
# store has no latitude/longitude in its master data. Per-store coordinates live
# in the store profile (backend/src/data/seed_stores.json), not here.
OPENWEATHERMAP_LAT = os.environ.get("OPENWEATHERMAP_LAT", "-6.2088")
OPENWEATHERMAP_LON = os.environ.get("OPENWEATHERMAP_LON", "106.8456")
OPENWEATHERMAP_UNITS = os.environ.get("OPENWEATHERMAP_UNITS", "metric")
OPENWEATHERMAP_TIMEOUT_SECONDS = float(os.environ.get("OPENWEATHERMAP_TIMEOUT_SECONDS", "5"))
OPENWEATHERMAP_MAX_RETRIES = int(os.environ.get("OPENWEATHERMAP_MAX_RETRIES", "3"))

# -------------------------------------------------------------
# Telegram Bot API (PRD Section 14.4)
# -------------------------------------------------------------
TELEGRAM_API_BASE_URL = os.environ.get("TELEGRAM_API_BASE_URL", "https://api.telegram.org")
TELEGRAM_TIMEOUT_SECONDS = float(os.environ.get("TELEGRAM_TIMEOUT_SECONDS", "10"))
# Optional hardcoded fallback for the local demo environment only.
# In Lambda the token is read from Secrets Manager and never from the environment.
TELEGRAM_BOT_TOKEN_FALLBACK = os.environ.get("TELEGRAM_BOT_TOKEN_FALLBACK", "")

# -------------------------------------------------------------
# Business Logic Defaults
# -------------------------------------------------------------
WEATHER_CACHE_TTL_HOURS = int(os.environ.get("WEATHER_CACHE_TTL_HOURS", "6"))
WEATHER_CACHE_VALID_HOURS = int(os.environ.get("WEATHER_CACHE_VALID_HOURS", "3"))
APPROVAL_TIMEOUT_HOURS = int(os.environ.get("APPROVAL_TIMEOUT_HOURS", "4"))
MAX_BEDROCK_RETRIES = int(os.environ.get("MAX_BEDROCK_RETRIES", "2"))
BEDROCK_MAX_TOKENS = int(os.environ.get("BEDROCK_MAX_TOKENS", "1024"))
BEDROCK_TEMPERATURE = float(os.environ.get("BEDROCK_TEMPERATURE", "0.2"))
PROMPT_VERSION = os.environ.get("PROMPT_VERSION", "v1.0")


def get_env(name: str, default: str = "") -> str:
    """Read an environment variable, tolerating missing/blank values."""
    return (os.environ.get(name) or "").strip() or default
