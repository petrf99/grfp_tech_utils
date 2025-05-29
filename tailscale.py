"""
Tailscale Integration Utilities
===============================

This module provides a complete cross-platform interface for working with the
Tailscale CLI and daemon (`tailscaled`). It includes:

- Discovery of the Tailscale binary (CLI and macOS GUI variants)
- Detection and startup of the `tailscaled` service if needed
- Bringing Tailscale up/down using an auth key and custom hostname
- Parsing Tailscale status output to retrieve peer IP addresses
- Retry and sudo-based fallback logic when permissions are insufficient

Supports Linux, macOS (CLI & GUI), and Windows environments.
"""

import os
import sys
import time
import json
import shlex
import shutil
import subprocess
from pathlib import Path
from dotenv import load_dotenv

from tech_utils.logger import init_logger
from tech_utils.safe_subp_run import safe_subp_run

logger = init_logger("Tailscale_TechUtils")
load_dotenv()

# === Internal Utility Functions ===

def find_gui_tailscale_path_macos() -> str | None:
    """Try to locate the macOS GUI Tailscale binary via Spotlight or standard folders."""
    try:
        result = subprocess.run(
            ["mdfind", "kMDItemCFBundleIdentifier == 'com.tailscale.ipn.macsys'"],
            capture_output=True, text=True
        )
        for app_path in result.stdout.strip().splitlines():
            candidate = os.path.join(app_path, "Contents", "MacOS", "Tailscale")
            if os.path.exists(candidate):
                return candidate
    except Exception:
        pass

    possible_dirs = [
        "/Applications",
        os.path.expanduser("~/Applications"),
        os.path.expanduser("~/Downloads"),
        "/Users/Shared",
    ]

    for directory in possible_dirs:
        if not os.path.exists(directory):
            continue
        for item in os.listdir(directory):
            if item.lower().startswith("tailscale") and item.endswith(".app"):
                candidate = os.path.join(directory, item, "Contents", "MacOS", "Tailscale")
                if os.path.exists(candidate):
                    return candidate

    fallback = os.getenv("MAC_GUI_TAILSCALE_PATH", "/Applications/Tailscale.app/Contents/MacOS/Tailscale")
    return fallback if os.path.exists(fallback) else None


def get_tailscale_path() -> str:
    """Locate the Tailscale CLI binary based on platform."""
    os_name = sys.platform

    if os_name.startswith("win"):
        try:
            result = subprocess.run(["where", "tailscale"], capture_output=True, text=True)
            if result.returncode == 0:
                path = result.stdout.strip().splitlines()[0]
                if os.path.exists(path):
                    return path
        except Exception:
            pass

    found = shutil.which("tailscale")
    if found and os.path.exists(found):
        return found

    if os_name == "darwin":
        gui_bin = find_gui_tailscale_path_macos()
        if gui_bin and os.path.exists(gui_bin):
            return gui_bin

    raise RuntimeError("❌ Tailscale binary not found on this system.")


def get_tailscaled_path():
    """Find the tailscaled binary if available (Linux/macOS only)."""
    path = shutil.which("tailscaled")
    if path and os.path.exists(path):
        return path

    fallback_paths = [
        str(Path.home() / os.getenv("TAILSCALED_PATH", ".homebrew/bin/tailscaled")),
    ]
    for alt_path in fallback_paths:
        if os.path.exists(alt_path):
            return alt_path

    return None


def is_tailscaled_running() -> bool:
    """Check if tailscaled daemon is running."""
    try:
        result = subprocess.run(["pgrep", "tailscaled"], capture_output=True, text=True)
        return result.returncode == 0
    except Exception as e:
        logger.warning(f"Error checking tailscaled status: {e}")
        return False


def is_tailscale_installed() -> str | bool:
    """Determine whether Tailscale is installed (CLI or macOS GUI)."""
    os_name = sys.platform

    if os_name.startswith("win"):
        try:
            result = subprocess.run(["where", "tailscale"], capture_output=True, text=True)
            return result.returncode == 0
        except Exception:
            return False

    if shutil.which("tailscale"):
        return True

    if os_name == "darwin":
        gui_path = find_gui_tailscale_path_macos()
        if gui_path and os.path.exists(gui_path):
            return 'macos-gui'

    return False

# === tailscaled Daemon Handling ===

def start_tailscaled_if_needed() -> bool:
    """Start tailscaled in background if it's not already running."""
    if is_tailscaled_running():
        return True

    logger.info("Starting tailscaled")
    path = get_tailscaled_path()
    if not path:
        logger.error("❌ tailscaled binary not found.")
        return False

    try:
        print(f"🚀 Starting tailscaled via: {path}")
        shell_cmd = f"nohup {shlex.quote(path)} --state=mem: >/dev/null 2>&1 &"
        sudo_cmd = ["sudo", "sh", "-c", shell_cmd]

        safe_subp_run(
            sudo_cmd, retries=3, timeout=5, delay_between_retries=3,
            check=True, text=True, stdin=sys.stdin
        )

        for _ in range(10):
            time.sleep(1.5)
            if is_tailscaled_running():
                print("✅ tailscaled is now running.")
                time.sleep(3)
                logger.info("tailscaled is now running")
                return True

        print("❌ tailscaled did not start within timeout.")
        logger.error("tailscaled did not start within timeout.")
        return False

    except Exception as e:
        logger.error(f"❌ Failed to start tailscaled: {e}")
        return False


# === Tailscale CLI Actions ===

def tailscale_up(hostname: str, auth_token: str) -> bool:
    """Start and authenticate Tailscale on this machine."""
    print("🔧 Starting Tailscale...")
    is_installed = is_tailscale_installed()
    if not is_installed:
        print("❌ Tailscale is not installed on this system.")
        logger.error(f"{hostname} Tailscale start failed — not installed")
        return False

    os_name = sys.platform
    mac_gui_flg = is_installed == 'macos-gui'

    if os_name.startswith(("linux", "darwin")) and not mac_gui_flg:
        if not start_tailscaled_if_needed():
            print("❌ Could not start tailscaled.")
            return False

    ts_path = get_tailscale_path()
    cmd = [ts_path, "up", f"--authkey={auth_token}", f"--hostname={hostname}"]

    try:
        logger.info(f"Starting tailscale for {hostname}")
        safe_subp_run(cmd, retries=3, timeout=5, delay_between_retries=3,
                      check=True, capture_output=True, text=True, shell=os_name.startswith("win"), enable_sudo_retry=True)
        print("✅ Tailscale started.")
        logger.info(f"{hostname} Tailscale start succeeded on {os_name}")
        return True

    except Exception as e:
        logger.error(f"Tailscale start failed with Exception {e}", exc_info=True)
        return False


def tailscale_down():
    """Disconnect from Tailscale and stop tailscaled if needed."""
    is_installed = is_tailscale_installed()
    if not is_installed:
        print("❌ Tailscale is not installed.")
        logger.warning("Tailscale disconnect skipped — not installed.")
        return

    mac_gui_flg = is_installed == 'macos-gui'
    os_name = sys.platform
    ts_path = get_tailscale_path()
    cmd = [ts_path, "down"]
    shell_flag = os_name.startswith("win")

    print("🔌 Disconnecting from Tailnet...")

    try:
        safe_subp_run(cmd, retries=3, timeout=5, delay_between_retries=3,
                      check=True, capture_output=True, text=True, shell=shell_flag, enable_sudo_retry=True)
        print("✅ Tailscale VPN disconnected.")
        logger.info("Tailscale VPN disconnected")

    except Exception as e:
        print("❌ Unexpected error while disconnecting Tailscale:", e)
        logger.exception(f"Unexpected error during Tailscale disconnect: {e}")

    if (not mac_gui_flg and os_name.startswith("darwin")) or os_name.startswith("linux"):
        if stop_tailscaled():
            print("🛑 tailscaled process stopped.")
            logger.info("tailscaled daemon process stopped.")
        else:
            print("⚠️ tailscaled was not running or could not be stopped.")


def stop_tailscaled() -> bool:
    """Stop tailscaled process via sudo kill."""
    try:
        result = subprocess.run(["pgrep", "tailscaled"], capture_output=True, text=True)
        if result.returncode != 0:
            return False

        for pid in result.stdout.strip().split():
            subprocess.run(["sudo", "kill", pid])
        return True
    except Exception as e:
        logger.warning(f"❌ Could not stop tailscaled: {e}")
        return False


# === Querying Peer IPs ===

def get_tailscale_ip_by_hostname(hostname: str, peer_flg: bool = True) -> str | None:
    """Query Tailscale IP for a given peer or local host by hostname."""
    try:
        ts_path = get_tailscale_path()
        result = subprocess.run(
            [ts_path, "status", "--json"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        data = json.loads(result.stdout)

        if peer_flg:
            peers = data.get("Peer", {}) or data.get("Peer[]", {})
            for peer_data in peers.values():
                if peer_data.get("HostName", "").split(".")[0] == hostname:
                    ips = peer_data.get("TailscaleIPs", [])
                    ipv4s = [ip for ip in ips if '.' in ip]
                    logger.info(f"Retrieved IPs {ipv4s} for hostname {hostname}")
                    return ipv4s[0] if ipv4s else None
        else:
            self_data = data.get("Self", {})
            if self_data.get("HostName", "").split(".")[0] == hostname:
                ips = self_data.get("TailscaleIPs", [])
                ipv4s = [ip for ip in ips if '.' in ip]
                logger.info(f"Retrieved self IPs {ipv4s} for hostname {hostname}")
                return ipv4s[0] if ipv4s else None

    except subprocess.CalledProcessError as e:
        logger.error(f"[!] Error executing tailscale: {e}")
    except json.JSONDecodeError as e:
        logger.error(f"[!] Failed to parse tailscale JSON output: {e}")
    except Exception as e:
        logger.error(f"[!] Unexpected error: {e}")

    return None


# === Manual Test Hook ===

if __name__ == '__main__':
    tailscale_up('test-client', os.getenv("TEST_CLIENT_AUTH_KEY"))
    tailscale_down()
