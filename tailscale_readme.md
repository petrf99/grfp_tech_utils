# Tailscale Utility for GCS

This module provides cross-platform utilities for controlling and interacting with [Tailscale](https://tailscale.com/) from within the Ground Control Station (GCS) project.

Supported platforms:
- ✅ Linux
- ✅ macOS (CLI and GUI)
- ✅ Windows

---

## ✨ Features

- 🔍 Auto-detection of `tailscale` and `tailscaled` binaries
- 🚀 Background launch of `tailscaled` when needed
- 🔐 Authenticated connection via `tailscale up --authkey`
- 🔌 Clean disconnection via `tailscale down`
- 🧼 Sudo fallback if permissions are insufficient
- 📡 Retrieve Tailscale IPv4 address of peers
- 🧪 Usable both as a library and a CLI script

---

## 🔧 Usage

### As a Python module

```python
from tailscale import tailscale_up, tailscale_down, get_tailscale_ip_by_hostname

# Start and authenticate with Tailscale
success = tailscale_up("drone-01", "tskey-...")

# Get the IPv4 address of a peer by hostname
ip = get_tailscale_ip_by_hostname("groundstation")

# Disconnect from Tailnet
tailscale_down()
```

## 🧪 CLI Testing

```bash
export TEST_CLIENT_AUTH_KEY="tskey-..."
python tailscale_techutils.py
```

## 📥 Dependencies

- **Tailscale CLI**
- **tailscaled** (Linux/macOS, unless using macOS GUI version)
- **Python libraries**:
  - `requests` (used indirectly)
  - `python-dotenv` (for loading `.env`)
- Your project’s `safe_subp_run` and `logger` modules

---

## 🌐 Environment Variables

| Variable               | Purpose                          |
|------------------------|----------------------------------|
| `TEST_CLIENT_AUTH_KEY` | Used for CLI testing (`up/down`) |

---

## 📝 Notes

- On macOS, GUI-based installs are auto-detected via Spotlight or known directories.
- On Linux/macOS, `tailscaled` will be started via `sudo nohup ... &` if not running.
- Interactive `sudo` is required for starting/stopping processes.
- Logging is handled via the project-wide logger.

---

## 🛑 Warnings

- Do **not** use this module if Tailscale is managed externally (e.g., via systemd).
- Avoid using this utility in environments where interactive `sudo` is not available.