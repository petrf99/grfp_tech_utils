import pytest
from unittest.mock import patch, MagicMock
from tech_utils.flask_server_utils import shutdown_server
from requests.exceptions import ConnectionError as RequestsConnectionError


# === Test: successful shutdown ===

@patch("requests.post")
def test_shutdown_server_success(mock_post):
    """Should return True and log success if shutdown request returns 200 OK."""
    mock_post.return_value.ok = True

    printed = []

    def fake_print(msg):
        printed.append(msg)

    result = shutdown_server(ip="127.0.0.1", port=9999, print_func=fake_print)

    assert result is True
    assert printed == ["Stopping TCP server...", "🔌 TCP server stopped."]


# === Test: server already stopped ===

@patch("requests.post", side_effect=RequestsConnectionError("Server not reachable"))
def test_shutdown_server_connection_error(mock_post):
    """Should return False and print warning if server is already stopped."""
    printed = []

    def fake_print(msg):
        printed.append(msg)

    result = shutdown_server(port=8888, print_func=fake_print)

    assert result is False
    assert any("not running" in msg.lower() for msg in printed)



# === Test: unexpected exception during shutdown ===

@patch("requests.post", side_effect=Exception("Boom"))
def test_shutdown_server_unexpected_exception(mock_post):
    """Should return False and print the exception message if request fails unexpectedly."""
    printed = []

    def fake_print(msg):
        printed.append(msg)

    result = shutdown_server(port=8080, print_func=fake_print)

    assert result is False
    assert any("failed" in msg.lower() for msg in printed)
    assert any("Boom" in msg for msg in printed)
    mock_post.assert_called_once()


# === Test: shutdown without print_func ===

@patch("requests.post")
def test_shutdown_server_no_print(mock_post):
    """Should not raise error if print_func is not provided."""
    mock_post.return_value.ok = True
    result = shutdown_server()
    assert result is True
