import subprocess
import time
import sys
from tech_utils.logger import init_logger

logger = init_logger("SafeSUBPRun_TechUtils")


def _needs_sudo_retry(stderr: str, os_name: str) -> bool:
    """Check if sudo retry is needed based on stderr output."""
    if not os_name.startswith(("linux", "darwin")):
        return False
    stderr = stderr.lower()
    return any(msg in stderr for msg in [
        "failed to connect to local tailscaled",
        "can't connect",
        "permission denied",
        "access denied",
        "connect: permission denied"
    ])


def safe_subp_run(
    command,
    retries=3,
    timeout=10,
    delay_between_retries=2,
    enable_sudo_retry=False,
    **kwargs
):
    """
    Runs a subprocess with a timeout and optional retries.
    Optionally retries with sudo on certain errors (Linux/macOS only).

    :param command: Command list (e.g., ['tailscale', 'up'])
    :param retries: Retry count before failure
    :param timeout: Timeout per attempt (seconds)
    :param delay_between_retries: Delay between retries
    :param enable_sudo_retry: Automatically retry with sudo if permissions are denied
    :param kwargs: Extra args passed to subprocess.run
    :return: subprocess.CompletedProcess or raises
    """
    os_name = sys.platform
    last_exception = None

    for attempt in range(1, retries + 1):
        try:
            logger.info(f"[{attempt}/{retries}] Running: {' '.join(command)}")
            result = subprocess.run(command, timeout=timeout, **kwargs)
            logger.info(f"✅ Subprocess <{' '.join(command)}> succeeded.")
            return result

        except subprocess.TimeoutExpired as e:
            logger.warning(f"[{attempt}] Subprocess: <{' '.join(command)}> Timeout: command took too long ({timeout}s)")
            last_exception = e

        except subprocess.CalledProcessError as e:
            logger.warning(f"[{attempt}] for subprocess <{' '.join(command)}> CalledProcessError: {e}")
            last_exception = e

            # Check if sudo retry is appropriate
            if enable_sudo_retry and _needs_sudo_retry(e.stderr or "", os_name):
                try:
                    sudo_cmd = ["sudo"] + command
                    logger.info(f"🔁 Retrying <{' '.join(command)}> with sudo: {' '.join(sudo_cmd)}")
                    sudo_result = subprocess.run(
                        sudo_cmd, timeout=timeout, **kwargs
                    )
                    logger.info(f"✅ Subprocess <{' '.join(command)}> with sudo succeeded.")
                    return sudo_result
                except subprocess.CalledProcessError as sudo_err:
                    logger.error(f"❌ Sudo retry for <{' '.join(command)}>failed: {sudo_err}")
                    last_exception = sudo_err
                except Exception as sudo_unexpected:
                    logger.error(f"❌ Unexpected error in sudo retry of <{' '.join(command)}>: {sudo_unexpected}")
                    last_exception = sudo_unexpected
            else:
                return e

        except Exception as e:
            logger.warning(f"[{attempt}] Unexpected exception for subprocess <{' '.join(command)}>: {e}")
            last_exception = e

        if attempt < retries:
            logger.info(f"Waiting {delay_between_retries}s before retry <{' '.join(command)}>...")
            time.sleep(delay_between_retries)

    logger.error(f"❌ All attempts failed for subprocess <{' '.join(command)}>.")
    raise last_exception
