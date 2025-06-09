import pytest
import requests
from unittest.mock import patch, MagicMock
from tech_utils.safe_post_req import post_request


# === Test: successful POST request ===

@patch("requests.post")
def test_post_request_success(mock_post):
    """Should return data if response is 200 and status is 'ok'."""
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"status": "ok", "data": 123}

    result = post_request(
        url="https://example.com/api",
        payload={"x": 1},
        description="Test request"
    )
    assert result == {"status": "ok", "data": 123}
    assert mock_post.call_count == 1


# === Test: POST fails with error response ===

@patch("requests.post")
def test_post_request_server_error(mock_post):
    """Should retry on 500+ response and return None eventually."""
    mock_post.return_value.status_code = 500
    mock_post.return_value.json.return_value = {"reason": "Server down"}

    result = post_request(
        url="https://example.com/api",
        payload={"x": 1},
        description="Test failure",
        retries=2,
        timeout=0
    )
    assert result is None
    assert mock_post.call_count == 2


# === Test: POST returns status 200 but JSON has no 'ok' status ===

@patch("requests.post")
def test_post_request_status_not_ok(mock_post):
    """Should retry if response is 200 but status is not 'ok'."""
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"status": "error"}

    result = post_request(
        url="https://example.com/api",
        payload={},
        description="Bad logic status",
        retries=2,
        timeout=0
    )
    assert result is None
    assert mock_post.call_count == 2


# === Test: exception during request ===

@patch("requests.post", side_effect=requests.RequestException("timeout"))
def test_post_request_exception(mock_post):
    """Should handle request exceptions and retry."""
    result = post_request(
        url="https://example.com/api",
        payload={},
        description="Network issue",
        retries=2,
        timeout=0
    )
    assert result is None
    assert mock_post.call_count == 2


# === Test: event_to_set aborts the request ===

@patch("requests.post")
def test_post_request_event_aborts_early(mock_post):
    """Should abort before first request if event is already set."""
    
    class DummyEvent:
        def __init__(self): self._is_set = False
        def is_set(self): return self._is_set
        def set(self): pass

    event = DummyEvent()
    result = post_request(
        url="https://example.com/api",
        payload={},
        description="Aborted request",
        event_to_set=event,
        retries=3
    )

    assert result is None
    assert mock_post.call_count == 0  # post should never be called



# === Test: print_func is called on error ===

@patch("requests.post", side_effect=requests.RequestException("boom"))
def test_post_request_calls_print_func_on_error(mock_post):
    """Should call print_func with message when request fails."""
    printed = []

    def fake_print(msg):
        printed.append(msg)

    result = post_request(
        url="https://example.com/api",
        payload={},
        description="Print test",
        print_func=fake_print,
        message="Something went wrong",
        retries=1,
        timeout=0
    )

    assert printed == ["Something went wrong"]
    assert result is None
