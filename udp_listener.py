import socket
import threading
import orjson
import time

from tech_utils.logger import init_logger
logger = init_logger("UDPListener")

class LatestValueBuffer:
    def __init__(self):
        self._lock = threading.Lock()
        self._value = None

    def set(self, val):
        with self._lock:
            self._value = val

    def get(self):
        with self._lock:
            val = self._value
            self._value = None
            return val

class UDPListener:
    def __init__(self, port, parse_json=True, bind_host="0.0.0.0"):
        self.port = port
        self.parse_json = parse_json
        self.buffer = LatestValueBuffer()

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind((bind_host, port))
        self._sock.settimeout(1.0)

        self._running = threading.Event()
        self._running.set()

        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def _listen_loop(self):
        while self._running.is_set():
            try:
                data, _ = self._sock.recvfrom(65536)
                if self.parse_json:
                    data = orjson.loads(data)
                self.buffer.set(data)
            except (orjson.JSONDecodeError, UnicodeDecodeError):
                continue
            except socket.timeout:
                continue
            except Exception as e:
                logger.error(f"[UDPListener] Error: {e}")

    def get_latest(self):
        return self.buffer.get()

    def stop(self):
        self._running.clear()
        try:
            self._sock.close()
        except:
            pass
        self._thread.join(timeout=1)
