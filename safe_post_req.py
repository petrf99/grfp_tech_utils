import requests
import time
from typing import Callable, Optional

from tech_utils.logger import init_logger
logger = init_logger("TechUtils_SafePOST")

def post_request(
    url: str,
    payload: dict,
    description: str,
    retries: int = 3,
    timeout: float = 1.0,
    event_to_set=None,
    print_func: Optional[Callable[[str], None]] = None,
    message: Optional[str] = None
):
    """
    Perform a POST request with retry logic, logging, and optional cancellation via event.

    Args:
        url: Target endpoint URL.
        payload: JSON-serializable request body.
        description: Text description for logging context.
        retries: Number of retry attempts (default: 3).
        timeout: Time (in seconds) between retries.
        event_to_set: Optional threading.Event to check and set on KeyboardInterrupt.
        print_func: Optional function to print user-facing messages (e.g., print).
        message: Optional message to print when a retry fails.

    Returns:
        Parsed response JSON dict if successful, otherwise None.
    """
    logger.info(f"Post request {description} to {url}: {payload}")
    try:
        for k in range(retries):
            if event_to_set and event_to_set.is_set():
                logger.warning(f"{description} aborted: event is set")
                return None
            try:
                response = requests.post(url, json=payload, timeout=20)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "ok":
                        logger.info(f"{description} — success")
                        return data
                else:
                    data = response.json()
                    reason = data.get("reason", "Unknown error")
                    logger.warning(f"{description} failed: {reason}")
                    if print_func and message:
                        print_func(message)
            except Exception as e:
                logger.error(f"{description} — could not reach url: {e}")
                if print_func and message:
                    print_func(message)

            time.sleep(timeout)

    except KeyboardInterrupt:
        if event_to_set:
            event_to_set.set()
        logger.warning(f"Aborted by keyboard interrupt during: {description}")

    return None
