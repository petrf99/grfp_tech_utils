import socket
import orjson
import time

from tech_utils.udp_listener import UDPListener, RingBuffer


# === RingBuffer ===

def test_ring_buffer_basic():
    buf = RingBuffer(max_size=2)
    buf.set("a", "addr1")
    buf.set("b", "addr2")
    assert buf.get() == "a"
    assert buf.get() == "b"
    assert buf.get() is None

def test_ring_buffer_overflow():
    buf = RingBuffer(max_size=1)
    buf.set("first", "addr1")
    buf.set("second", "addr2")  # 'first' должен быть вытеснен
    assert buf.get() == "second"
    assert buf.get() is None

def test_ring_buffer_with_addr():
    buf = RingBuffer(max_size=1)
    buf.set("value", "127.0.0.1")
    assert buf.get(with_addr=True) == ("value", "127.0.0.1")


# === UDPListener ===

def send_udp_message(port, payload: bytes):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(payload, ("127.0.0.1", port))
    sock.close()

def test_udp_listener_receives_json():
    listener = UDPListener(port=9999, parse_json=True, buffer_max_size=5)

    test_data = {"msg": "hello"}
    send_udp_message(9999, orjson.dumps(test_data))

    time.sleep(0.1)  # дать потоку время получить данные
    result = listener.get_latest()
    assert result == test_data

    listener.stop()

def test_udp_listener_handles_invalid_json():
    listener = UDPListener(port=9998, parse_json=True)
    
    send_udp_message(9998, b"{this is not valid json}")

    time.sleep(0.1)
    assert listener.get_latest() is None  # сообщение должно быть проигнорировано

    listener.stop()

def test_udp_listener_with_addr():
    listener = UDPListener(port=9997, parse_json=True, save_addr=True)

    test_data = {"msg": "with addr"}
    send_udp_message(9997, orjson.dumps(test_data))

    time.sleep(0.1)
    val, addr = listener.get_latest(with_addr=True)
    assert val == test_data
    assert isinstance(addr, tuple)  # ('127.0.0.1', port)

    listener.stop()

def test_udp_listener_stop_gracefully():
    listener = UDPListener(port=9996, parse_json=True)
    listener.stop()

    assert not listener._running.is_set()
    assert not listener._thread.is_alive()
