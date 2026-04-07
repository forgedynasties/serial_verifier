# Serial Verification Tool (Linux GUI)

This tool is an automatic, continuous verification station for Android devices:

1. Detects connected ADB devices automatically.
2. As soon as exactly one device is detected, it reboots that device automatically.
3. While reboot is in progress, waits for barcode scan.
4. Captures barcode automatically when input reaches exactly `14` characters (no Enter required).
5. Compares barcode serial vs ADB serial from rebooted device.
6. If barcode does not match, keeps the same device active and allows barcode re-scan.
7. Returns to ready state for next verification cycle after a PASS result.

## Requirements

- Linux desktop with Python 3
- PyQt5 (`python3-pyqt5`)
- Android platform tools (`adb`) installed and available in `PATH`
- One Android device connected at a time
- Barcode scanner configured as keyboard input (Enter is not required)

Install GUI dependency on Debian/Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y python3-pyqt5
```

## Run

```bash
python3 serial_verification_gui.py
```

or

```bash
python3 -m serial_verifier
```

## Build Linux Desktop App (optional)

This bundles the app into a single Linux executable and installs a `.desktop`
launcher with an icon so it appears in the application menu.

1. Install PyInstaller:

```bash
python3 -m pip install --user pyinstaller
```

2. Build the binary:

```bash
./scripts/build_linux_app.sh
```

3. Install the local launcher:

```bash
./scripts/install_local.sh
```

Notes:
- The window icon is set in code and is embedded in the app.
- The launcher icon is generated from `app_icon.ico` if Pillow is available;
  otherwise it falls back to `aio.png`.

Uninstall the local launcher:

```bash
./scripts/uninstall_local.sh
```

## Build .deb Package (optional)

This creates a Debian package that installs the app to `/usr/bin` and adds a
desktop launcher + icon.

```bash
./scripts/build_deb.sh
```

Optional env overrides:

```bash
APP_VERSION=1.0.0 ARCH=amd64 ./scripts/build_deb.sh
```

## Build Zip Bundle (optional)

This creates a portable zip that includes the app binary + bundled adb tools.

```bash
./scripts/build_zip.sh
```

You can override the platform-tools path:

```bash
PLATFORM_TOOLS_DIR=../platform-tools ./scripts/build_zip.sh
```

After extracting the zip, run `setup.sh` once to install the local launcher.

### PEP 668 / Externally Managed Python

If `pip install` is blocked by PEP 668, the build scripts will automatically
create a local `.venv` and install PyInstaller there. The build also needs
PyQt5 available in the build environment so it can be bundled. If setup fails,
install:

```bash
sudo apt-get install -y python3-venv python3-pyqt5
```

## Operator Flow

1. Launch the app.
2. Connect one device (auto-detected in the GUI).
3. Wait while the app automatically starts reboot + reconnect handling.
4. Scan barcode; once 14 characters are read it is captured automatically.
5. If FAIL/ERROR appears for barcode mismatch, scan again for the same device.
6. When PASS appears, disconnect and connect next device to trigger the next automatic cycle.

## UI Behavior

- Auto device detection
- Automatic reboot workflow when one device is detected
- Auto barcode capture at 14 characters (no Enter key)
- Barcode retry support for the same connected device after mismatch
- Live status and timestamped logs
- Last result details (barcode, ADB serial, outcome)
- History table for recent checks
- Running counters: total, pass, fail, errors

## Project Structure

```text
serial_verification_gui.py      # thin launcher
serial_verifier/
  __init__.py
  gui.py                        # PyQt UI
  device_monitor.py             # background adb device monitor
  service.py                    # verification workflow orchestration
  adb_client.py                 # adb command wrapper
  models.py                     # result models
  errors.py                     # custom exceptions
  config.py                     # timeout/polling configuration
```
