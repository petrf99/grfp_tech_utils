import requests
from tech_utils.logger import init_logger

_logger = init_logger("FlaskServUtils")

def shutdown_server(ip="127.0.0.1", port=8000, print_func = None, logger = _logger):
    """
    Gracefully shutdown the Flask server.
    """
    if print_func:
        print_func("Stopping TCP server...")
    try:
        res = requests.post(f"http://{ip}:{port}/shutdown", timeout=3)
        if res.ok:
            logger.info("TCP server stopped")
            if print_func:
                print_func("🔌 TCP server stopped.")
        return True
    except requests.exceptions.ConnectionError:
        logger.error("TCP server not running (already stopped)")
        if print_func:
            print_func("⚠️ TCP server not running (already stopped).")
    except Exception as e:
        logger.error(f"Failed to shutdown TCP server: {e}")
        if print_func:
            print_func(f"⚠️ Failed to shutdown TCP server: {e}")
    return False