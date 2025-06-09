import hid

def is_gamepad_like(device):
    return device.get('usage_page') == 1 and device.get('usage') in (4, 5)

def is_reasonable_controller(device):
    name = (device.get('product_string') or '').lower()
    manufacturer = (device.get('manufacturer_string') or '').lower()

    keywords = ['joystick', 'gamepad', 'rc', 'controller', 'drone', 'fly', 'taranis', 'frsky', 'spektrum', 'radiomaster']
    return any(k in name or k in manufacturer for k in keywords)

def is_valid_device(device):
    return is_gamepad_like(device) or is_reasonable_controller(device)

class HidDevices:
    def __init__(self):
        self.refresh()

    def output_hid_list(self, printf=print):
        for d in self.devices:
            printf(f"Vendor ID     : {hex(d['vendor_id'])}")
            printf(f"Product ID    : {hex(d['product_id'])}")
            printf(f"Manufacturer  : {d.get('manufacturer_string', 'Unknown')}")
            printf(f"Product       : {d.get('product_string', 'Unknown')}")
            printf(f"Serial Number : {d.get('serial_number', 'None')}")
            path = d['path']
            if isinstance(path, bytes):
                path = path.decode('utf-8', errors='ignore')
            printf(f"Path          : {path}")
            printf("-" * 40)

    def refresh(self):
        devices_raw = hid.enumerate()
        self.devices = []
        for d in devices_raw:
            if is_valid_device(d):
                self.devices.append(d)
        self.n_devices = len(self.devices)

    def short_names(self):
        shn = []
        for d in self.devices:
            name = f"{d.get('manufacturer_string', 'Unknown')} {d.get('product_string', 'Unknown')}"
            shn.append(name)
        return shn 

    def select_device(self, device_num):
        d = self.devices[device_num]
        path = d['path']
        if isinstance(path, str) or isinstance(path, bytes):
            return hid.Device(path=path)
        else:
            raise ValueError("Invalid path type for HID device.")
    
    def select_device_by_name(self, device_name):
        shn = self.short_names()
        device_num = None
        for k in range(len(shn)):
            if device_name == shn[k]:
                device_num = k
                break
        if device_num is not None:
            return self.select_device(device_num)
        else:
            return None
        
    def get_id_by_name(self, device_name):
        for d in self.devices:
            if f"{d.get('manufacturer_string', 'Unknown')} {d.get('product_string', 'Unknown')}" == device_name:
                return (d.get('vendor_id', None), d.get('product_id', None))
        return None

