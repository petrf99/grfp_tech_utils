import subprocess
import pytest
from unittest.mock import patch, MagicMock, call
from tech_utils.safe_subp_run import safe_subp_run, _needs_sudo_retry


# === Test: _needs_sudo_retry ===

@pytest.mark.parametrize("stderr,platform,expected", [
    ("Permission denied", "linux", True),
    ("connect: permission denied", "darwin", True),
    ("Some unrelated error", "linux", False),
    ("Permission denied", "win32", False),
])
def test_needs_sudo_retry(stderr, platform, expected):
    """Validate which stderr messages require sudo retry on Unix systems."""
    assert _needs_sudo_retry(stderr, platform) == expected


# === Test: safe_subp_run success ===

@patch("subprocess.run")
def test_safe_subp_run_success(mock_run):
    """Should return result immediately if subprocess succeeds."""
    mock_result = MagicMock()
    mock_run.return_value = mock_result

    result = safe_subp_run(["echo", "hello"], retries=2, timeout=1)
    assert result == mock_result
    assert mock_run.call_count == 1


# === Test: safe_subp_run retry on TimeoutExpired ===

@patch("time.sleep")  # Skip real delays
@patch("subprocess.run", side_effect=[subprocess.TimeoutExpired(cmd="test", timeout=1),
                                      subprocess.CompletedProcess(args="test", returncode=0)])
def test_safe_subp_run_retries_on_timeout(mock_run, _):
    """Should retry once if subprocess times out and then succeed."""
    result = safe_subp_run(["echo", "test"], retries=2, timeout=1)
    assert isinstance(result, subprocess.CompletedProcess)
    assert mock_run.call_count == 2


# === Test: safe_subp_run fails after all retries ===

@patch("time.sleep")
@patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="test", timeout=1))
def test_safe_subp_run_all_retries_fail(mock_run, _):
    """Should raise exception after all retries exhausted."""
    with pytest.raises(subprocess.TimeoutExpired):
        safe_subp_run(["echo", "fail"], retries=3, timeout=1)
    assert mock_run.call_count == 3


# === Test: safe_subp_run retries with sudo on permission error ===

@patch("sys.platform", "linux")
@patch("time.sleep")
@patch("subprocess.run")
def test_safe_subp_run_sudo_retry_success(mock_run, _sleep, monkeypatch):
    """Should retry with sudo if permission error detected, and succeed."""
    # First call fails with permission denied
    error = subprocess.CalledProcessError(1, cmd=["somecmd"], stderr="permission denied")
    mock_run.side_effect = [error, subprocess.CompletedProcess(args=["sudo", "somecmd"], returncode=0)]

    result = safe_subp_run(["somecmd"], retries=1, timeout=2, enable_sudo_retry=True)

    assert isinstance(result, subprocess.CompletedProcess)
    assert mock_run.call_count == 2
    assert mock_run.call_args_list[1][0][0][0] == "sudo"  # Ensure sudo was added


# === Test: safe_subp_run fails sudo retry too ===

@patch("sys.platform", "linux")
@patch("time.sleep")
@patch("subprocess.run", side_effect=[
    subprocess.CalledProcessError(1, cmd=["cmd"], stderr="permission denied"),
    subprocess.CalledProcessError(1, cmd=["sudo", "cmd"], stderr="still fails")
])
def test_safe_subp_run_sudo_retry_failure(mock_run, _):
    """Should raise the final sudo error if sudo retry also fails."""
    with pytest.raises(subprocess.CalledProcessError):
        safe_subp_run(["cmd"], retries=1, timeout=2, enable_sudo_retry=True)
    assert mock_run.call_count == 2


# === Test: safe_subp_run returns CalledProcessError without sudo retry ===

@patch("time.sleep")
@patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, cmd="cmd", stderr="some error"))
def test_safe_subp_run_no_sudo_retry(mock_run, _):
    """Should return CalledProcessError if sudo retry is disabled."""
    result = safe_subp_run(["cmd"], retries=1, timeout=1, enable_sudo_retry=False)
    assert isinstance(result, subprocess.CalledProcessError)
    assert mock_run.call_count == 1
