import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def get_resilient_http_session(
    total_retries: int = 3,
    backoff_factor: float = 0.6,
) -> requests.Session:
    """
    Membuat HTTP Session dengan Exponential Backoff Retry.
    Hanya me-retry error transien (429, 502, 503, 504) dan tidak me-retry 400/401/403.
    """
    session = requests.Session()
    retry_strategy = Retry(
        total=total_retries,
        connect=total_retries,
        read=total_retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


http_session = get_resilient_http_session()