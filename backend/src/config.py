"""Configuration & Environment Settings for AutoReplenish.ai."""

import os
import logging
from typing import Dict, Any, Optional

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

# Secret Names
WEATHER_SECRET_NAME = os.environ.get("WEATHER_SECRET_NAME", f"autoreplenish/weather-credentials-{ENVIRONMENT}")
TELEGRAM_SECRET_NAME = os.environ.get("TELEGRAM_SECRET_NAME", f"autoreplenish/telegram-credentials-{ENVIRONMENT}")
SAP_SECRET_NAME = os.environ.get("SAP_SECRET_NAME", f"autoreplenish/sap-credentials-{ENVIRONMENT}")
SAP_PR_QUEUE_URL = os.environ.get("SAP_PR_QUEUE_URL", "")

# Business Logic Defaults
WEATHER_CACHE_TTL_HOURS = 6
WEATHER_CACHE_VALID_HOURS = 3
APPROVAL_TIMEOUT_HOURS = 4
MAX_BEDROCK_RETRIES = 2
PROMPT_VERSION = "v1.0"
