import time
import socket
from tech_utils.udp_listener import UDPListener

from tech_utils.logger import init_logger
logger = init_logger(name="UDP_Proxy", component='tech_utils')

def udp_proxy_loop(listen_ip, listen_port, target_ip, target_port, buffer_max_size = 1, ip_whitelist = [], stop_events = [], status_event = None, name="UDP Proxy", log_delay = 1, transformer = lambda x: x, sock_timeout = 0.01):
    with_addr = bool(ip_whitelist)
    listener = UDPListener(port=listen_port, parse_json=False, bind_host=listen_ip, save_addr=with_addr, buffer_max_size=buffer_max_size)
    sock = listener.get_sock()
    logger.info(f"{name} UDP-listening on {listen_ip}:{listen_port} → {target_ip}:{target_port}")

    last_inp_log_time = 0
    try:
        if status_event:
            status_event.set()
        while all(event.is_set() for event in stop_events):
            if status_event.is_set():
                try:

                    res = listener.get_latest(with_addr=with_addr)
                    #logger.debug(f"{name}, {with_addr}, {res}")
                    if res is None:
                        time.sleep(0.001)
                        continue

                    if with_addr:
                        data, addr = res
                        ip, port = addr
                        if ip_whitelist and ip not in ip_whitelist:
                            logger.info(f"{name} UDP Proxy: Address {ip}:{port} is not in white list")
                            continue
                    else:
                        data = res
                        addr = None

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
        listener.stop() 