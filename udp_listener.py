import socket
import threading
import orjson
import time

from tech_utils.logger import init_logger
logger = init_logger(name="UDPListener", component="tech_utils")

from collections import deque
from threading import Lock

class RingBuffer:
    def __init__(self, max_size=1):
        self._deque = deque(maxlen=max_size)
        self._lock = Lock()

    def set(self, val, addr):
        """Добавить значение (val[, addr]) в буфер.
        Старое будет отброшено, если буфер заполнен.
        """
        with self._lock:
            self._deque.append((val, addr))

    def get(self, with_addr=False):
        """Получить следующее значение из буфера (FIFO).
        Вернёт None, если буфер пуст.
        """
        with self._lock:
            if not self._deque:
                return None
            val, addr = self._deque.popleft()
            return (val, addr) if with_addr else val
        

class UDPListener:
    def __init__(self, port, parse_json=True, bind_host="0.0.0.0", save_addr=False, buffer_max_size = 1):
        self.port = port
        self.save_addr = save_addr
        self.parse_json = parse_json
        self.buffer = RingBuffer(buffer_max_size)

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind((bind_host, port))
        self._sock.settimeout(1.0)

        self._running = threading.Event()
        self._running.set()

        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def _listen_loop(self):
        logger.info("[UDPListener] Listen loop started")
        while self._running.is_set():
            try:
                data, addr = self._sock.recvfrom(65536)
                if self.parse_json:
                    data = orjson.loads(data)
                self.buffer.set(data, addr)
            except (orjson.JSONDecodeError, UnicodeDecodeError):
                continue
            except socket.timeout:
                continue
            except Exception as e:
                if not self._running.is_set():
                    break
                logger.error(f"[UDPListener] Error: {e}")

    def get_latest(self, with_addr=False):
        return self.buffer.get(with_addr=with_addr)

    def stop(self):
        self._running.clear()
        try:
            self._sock.close()
        except:
            pass
        self._thread.join(timeout=1)

    def get_sock(self):
        return self._sock
