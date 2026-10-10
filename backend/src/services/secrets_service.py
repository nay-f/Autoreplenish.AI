"""AWS Secrets Manager resolution with per-container caching.

Keeps API credentials out of source and environment variables (PRD Section 24:
"Jangan hardcode secrets"). Retrieved secrets are cached in-process for the
lifetime of the warm Lambda container to avoid Secrets Manager rate limits and
latency on hot paths.
"""

import json
from typing import Any, Dict, Optional

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from ..config import logger, AWS_REGION, get_env

DEFAULT_CACHE_TTL_SECONDS = 900  # 15 minutes


class SecretManagerService:
    """Cached reader for Secrets Manager string secrets (JSON payloads)."""

    def __init__(self, boto3_client: Optional[Any] = None, cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS):
        self._client = boto3_client or boto3.client(
            "secretsmanager",
            region_name=AWS_REGION,
            config=BotoConfig(retries={"max_attempts": 3, "mode": "standard"}),
        )
        self._cache_ttl_seconds = cache_ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cached_at: Dict[str, float] = {}

    def get_secret_json(self, secret_name: str) -> Dict[str, Any]:
        """Return the parsed JSON body of a secret, or {} when unreachable."""
        import time

        now = time.time()
        cached = self._cache.get(secret_name)
        if cached is not None and (now - self._cached_at.get(secret_name, 0)) < self._cache_ttl_seconds:
            return cached

        try:
            response = self._client.get_secret_value(SecretId=secret_name)
            secret_string = response.get("SecretString")
            if not secret_string:
                return {}
            parsed = json.loads(secret_string)
            if isinstance(parsed, dict):
                self._cache[secret_name] = parsed
                self._cached_at[secret_name] = now
                return parsed
            return {}
        except ClientError as e:
            logger.error(f"Failed to read secret '{secret_name}': {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error reading secret '{secret_name}': {e}")
            return {}

    # Convenience accessors -------------------------------------------------
    def get_weather_api_key(self, secret_name: str) -> str:
        secrets = self.get_secret_json(secret_name)
        return str(secrets.get("api_key") or get_env("OPENWEATHERMAP_API_KEY", ""))

    def get_telegram_bot_token(self, secret_name: str) -> str:
        secrets = self.get_secret_json(secret_name)
        return str(secrets.get("bot_token") or get_env("TELEGRAM_BOT_TOKEN", ""))

    def get_telegram_chat_id(self, secret_name: str) -> str:
        secrets = self.get_secret_json(secret_name)
        return str(secrets.get("chat_id") or secrets.get("admin_chat_id") or get_env("TELEGRAM_CHAT_ID", ""))

    def get_telegram_webhook_secret(self, secret_name: str) -> str:
        secrets = self.get_secret_json(secret_name)
        return str(secrets.get("webhook_secret") or "")

    def get_sap_credentials(self, secret_name: str) -> Dict[str, Any]:
        secrets = self.get_secret_json(secret_name)
        return {
            "client_id": str(secrets.get("client_id") or ""),
            "client_secret": str(secrets.get("client_secret") or ""),
            "token_url": str(secrets.get("token_url") or ""),
            "odata_base_url": str(secrets.get("odata_base_url") or ""),
            "sap_client": str(secrets.get("sap_client") or "100"),
        }

    @staticmethod
    def has_live_credentials(creds: Dict[str, Any]) -> bool:
        """True when the SAP secret contains a usable LIVE endpoint + credentials."""
        return bool(creds.get("client_id") and creds.get("client_secret") and creds.get("odata_base_url"))
