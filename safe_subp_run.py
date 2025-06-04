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
            logger.warning(f"[{attempt}] Subprocess: <{' '.join(command)}> Timeout: command took too long ({timeout}s)")
            last_exception = e

        except subprocess.CalledProcessError as e:
            logger.warning(f"[{attempt}] for subprocess <{' '.join(command)}> CalledProcessError: {e}")
            last_exception = e
            # Check if sudo retry is appropriate
            if enable_sudo_retry and _needs_sudo_retry(e.stderr or "", os_name):
                if os_name.startswith("darwin"): # Run via AppleScript official widget
                    quoted_cmd = " ".join(command).replace('"', '\\"')
                    applescript = applescript = (
                        f"do shell script \"{quoted_cmd}\" "
                        f"with administrator privileges "
                        f"with prompt \"{promt}\""
                    )

                    logger.info(f"🔁 Retrying via AppleScript: {applescript}")
                    try:
                        if background:
                            return subprocess.Popen(["osascript", "-e", applescript], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        else:
                            return subprocess.run(
                                ["osascript", "-e", applescript],
                                timeout=timeout,
                                capture_output=True,
                                text=True
                            )
                    except Exception as apple_err:
                        logger.error(f"❌ AppleScript sudo failed: {apple_err}")
                        last_exception = apple_err
                else: # Normal sudo fallback
                    try:
                        sudo_cmd = ["sudo"] + command
                        logger.info(f"🔁 Retrying <{' '.join(command)}> with sudo: {' '.join(sudo_cmd)}")
                        if background:
                            sudo_result = subprocess.Popen(sudo_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        else:
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


if __name__ == '__main__':
    #print(_needs_sudo_retry(["ifconfig", "lo0", "down"], "darwin"))
    safe_subp_run(["ifconfig", "lo0", "down"], enable_sudo_retry=True, check=True, capture_output=True, text=True)