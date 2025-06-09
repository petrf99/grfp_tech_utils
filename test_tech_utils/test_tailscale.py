import sys
import json
import pytest
from unittest.mock import patch, MagicMock
from unittest.mock import patch

import tech_utils.tailscale as ts


# === Test: find_gui_tailscale_path_macos ===

@patch("os.path.exists", return_value=True)
@patch("subprocess.run")
def test_find_gui_tailscale_path_macos_spotlight(mock_run, mock_exists):
    """Should return valid GUI path from Spotlight."""
    mock_run.return_value.stdout = "/Applications/Tailscale.app\n"
    result = ts.find_gui_tailscale_path_macos()
    assert result.endswith("MacOS/Tailscale")


@patch("os.listdir", return_value=["Tailscale.app"])
@patch("os.path.exists", return_value=True)
def test_find_gui_tailscale_path_macos_fallback(mock_exists, mock_listdir):
    """Should return fallback path when Spotlight fails."""
    result = ts.find_gui_tailscale_path_macos()
    assert isinstance(result, str)


# === Test: get_tailscaled_path ===

@patch("os.path.exists", side_effect=lambda p: ".homebrew/bin/tailscaled" in p)
@patch("shutil.which", return_value=None)
def test_get_tailscaled_path_fallback(mock_which, mock_exists):
    """Should find tailscaled in fallback home path."""
    result = ts.get_tailscaled_path()
    assert ".homebrew/bin/tailscaled" in result


# === Test: is_tailscaled_running ===

@patch("subprocess.run")
def test_is_tailscaled_running_true(mock_run):
    """Should return True if pgrep finds the process."""
    mock_run.return_value.returncode = 0
    assert ts.is_tailscaled_running() is True


@patch("subprocess.run", side_effect=Exception("fail"))
def test_is_tailscaled_running_failure(mock_run):
    """Should handle subprocess error and return False."""
    assert ts.is_tailscaled_running() is False


# === Test: is_tailscale_installed ===

def test_is_tailscale_installed_macos_gui_with_monkeypatch(monkeypatch):
    """Should detect macOS GUI version using monkeypatch on sys.platform."""
    
    # Pretend we are on macOS
    monkeypatch.setattr(sys, "platform", "darwin")

    # Patch other dependencies using context manager
    with patch("os.path.exists", return_value=True), \
         patch("shutil.which", return_value=None), \
         patch("tech_utils.tailscale.find_gui_tailscale_path_macos", return_value="/Applications/Tailscale.app/Contents/MacOS/Tailscale"):
        
        result = ts.is_tailscale_installed()
        assert result == "macos-gui"



@patch("shutil.which", return_value="/usr/bin/tailscale")
def test_is_tailscale_installed_cli(mock_which):
    """Should detect CLI as installed."""
    assert ts.is_tailscale_installed() is True


# === Test: get_tailscale_ip_by_hostname ===

@patch("tech_utils.tailscale.get_tailscale_path", return_value="/usr/bin/tailscale")
@patch("subprocess.run")
def test_get_tailscale_ip_by_hostname_peer(mock_run, _):
    """Should extract peer IP from Tailscale JSON status."""
    mock_run.return_value.stdout = json.dumps({
        "Peer": {
            "peer-123": {
                "HostName": "drone.local",
                "TailscaleIPs": ["100.100.100.1"]
            }
        }
    })
    result = ts.get_tailscale_ip_by_hostname("drone")
    assert result == "100.100.100.1"


@patch("tech_utils.tailscale.get_tailscale_path", return_value="/usr/bin/tailscale")
@patch("subprocess.run")
def test_get_tailscale_ip_by_hostname_self(mock_run, _):
    """Should extract local IP from Tailscale JSON status when peer_flg=False."""
    mock_run.return_value.stdout = json.dumps({
        "Self": {
            "HostName": "client.local",
            "TailscaleIPs": ["100.64.0.1"]
        }
    })
    result = ts.get_tailscale_ip_by_hostname("client", peer_flg=False)
    assert result == "100.64.0.1"
