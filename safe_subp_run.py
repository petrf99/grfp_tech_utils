import subprocess
import time
import sys
import os
from dotenv import load_dotenv
load_dotenv()
from tech_utils.logger import init_logger

logger = init_logger(name="SafeSUBPRun", component="tech_utils")

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
        "connect: permission denied",
        "not permitted",
        "root"
    ])


def safe_subp_run(
    command,
    retries=3,
    timeout=10,
    delay_between_retries=2,
    enable_sudo_retry=False,
    promt='Please enter your password to continue',
    background=False,
    cli_mode=os.getenv("CLI_MODE", "False") == "True",  # <== Новый флаг
    **kwargs
):
    """
    Runs a subprocess with a timeout and optional retries.
    Optionally retries with sudo or GUI elevation on certain errors (Linux/macOS only).

    :param command: Command list (e.g., ['tailscale', 'up'])
    :param cli_mode: Use CLI sudo instead of GUI pkexec/osascript (default: False)
    :param kwargs: Extra args passed to subprocess.run
    """
    os_name = sys.platform
    last_exception = None

    for attempt in range(1, retries + 1):
        try:
            logger.info(f"[{attempt}/{retries}] Running: {' '.join(command)}")
            if background:
                p = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                time.sleep(1)
                retcode = p.poll()
                if retcode is not None:
                    stderr = p.stderr.read().decode()
                    raise subprocess.CalledProcessError(
                        returncode=retcode,
                        cmd=command,
                        stderr=stderr
                    )
            else:
                p = subprocess.run(command, timeout=timeout, **kwargs)
            logger.info(f"✅ Subprocess <{' '.join(command)}> succeeded.")
            return p

        except subprocess.TimeoutExpired as e:
            logger.warning(f"[{attempt}] Subprocess: <{' '.join(command)}> Timeout after {timeout}s")
            last_exception = e

        except subprocess.CalledProcessError as e:
            logger.warning(f"[{attempt}] CalledProcessError: {e}")
            last_exception = e

            if enable_sudo_retry and _needs_sudo_retry(e.stderr or "", os_name):
                try:
                    if cli_mode:
                        sudo_cmd = ["sudo"] + command
                        logger.info(f"🔁 Retrying with CLI sudo: {' '.join(sudo_cmd)}")
                        if background:
                            return subprocess.Popen(sudo_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        else:
                            return subprocess.run(sudo_cmd, timeout=timeout, **kwargs)

                    elif os_name.startswith("darwin"):
                        quoted_cmd = " ".join(command).replace('"', '\\"')
                        applescript = (
                            f'do shell script "{quoted_cmd}" '
                            f'with administrator privileges '
                            f'with prompt "{promt}"'
                        )
                        logger.info(f"🔁 Retrying via AppleScript: {applescript}")
                        if background:
                            return subprocess.Popen(["osascript", "-e", applescript],
                                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        else:
                            return subprocess.run(["osascript", "-e", applescript],
                                                  timeout=timeout, capture_output=True, text=True)

                    elif os_name.startswith("linux"):
                        pkexec_cmd = ["pkexec"] + command
                        logger.info(f"🔁 Retrying via pkexec: {' '.join(pkexec_cmd)}")
                        if background:
                            return subprocess.Popen(pkexec_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        else:
                            return subprocess.run(pkexec_cmd, timeout=timeout, **kwargs)

                    else:
                        logger.error("❌ Unsupported OS for retry")
                except Exception as retry_err:
                    logger.error(f"❌ Retry with elevation failed: {retry_err}")
                    last_exception = retry_err
            else:
                return e

        except Exception as e:
            logger.warning(f"[{attempt}] Unexpected exception: {e}")
            last_exception = e

        if attempt < retries:
            logger.info(f"Waiting {delay_between_retries}s before retry...")
            time.sleep(delay_between_retries)

    logger.error(f"❌ All attempts failed for command: {' '.join(command)}")
    raise last_exception
