import socket
import time

from tech_utils.logger import init_logger
logger = init_logger("UDP_Proxy")

def udp_proxy_loop(listen_ip, listen_port, target_ip, target_port, ip_whitelist = [], stop_events = [], status_event = None, name="UDP Proxy", log_delay = 1, transformer = lambda x: x, sock_timeout = 0.01):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((listen_ip, listen_port))
    sock.settimeout(sock_timeout)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    logger.info(f"{name} UDP-listening on {listen_ip}:{listen_port} → {target_ip}:{target_port}")

    last_inp_log_time = 0
    try:
        if status_event:
            status_event.set()
        while not any(event.is_set() for event in stop_events):
            if status_event.is_set():
                try:
                    data, addr = sock.recvfrom(65536)  # max UDP size
                    ip, port = addr
                    if ip not in ip_whitelist and ip_whitelist != []:
                        logger.info(f"{name} UDP Proxy: Address {ip}:{port} is not in white list")
                        continue
                    sock.sendto(transformer(data), (target_ip, target_port))
                    cur_time = time.time()
                    if cur_time - last_inp_log_time >= log_delay:
                        logger.info(f"{name} UDP-forwarded {len(data)} bytes from {addr} to {target_ip}:{target_port}")
                        last_inp_log_time = cur_time
                except socket.timeout:
                    pass
            
    except KeyboardInterrupt:
        logger.warning(f"🛑 {name} stopped by user.")
    except Exception as e:
        logger.error(f"⚠️ {name} error: {e}")
    finally:
        if status_event:
            status_event.clear()
        sock.close()