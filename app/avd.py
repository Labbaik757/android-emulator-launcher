"""Create / list / launch / delete / clone Android Virtual Devices."""
import os
import shutil
import subprocess
import sys

from . import config, sdk

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def _run(cmd, **kwargs):
    kwargs.setdefault("creationflags", CREATE_NO_WINDOW)
    return subprocess.run(cmd, **kwargs)


def list_avds(sdk_dir=None):
    paths = sdk.sdk_paths(sdk_dir)
    r = _run([paths["emulator"], "-list-avds"], capture_output=True, text=True, timeout=60)
    return [l.strip() for l in r.stdout.splitlines() if l.strip()]


def create_avd(name, log, sdk_dir=None, ram_mb=None):
    paths = sdk.sdk_paths(sdk_dir)
    log(f"Creating virtual device '{name}'...")
    # "no" = don't use a custom hardware profile.
    r = _run(
        [
            paths["avdmanager"], "create", "avd",
            "-n", name,
            "-k", config.SYSTEM_IMAGE,
            "-d", config.DEVICE_PROFILE,
            "--force",
        ],
        input="no\n",
        text=True,
        capture_output=True,
        timeout=600,
    )
    log((r.stdout + r.stderr)[-2000:])
    if r.returncode != 0:
        raise RuntimeError(f"avdmanager failed (exit {r.returncode}).")
    _set_ram_size(name, ram_mb or config.DEVICE_RAM_MB, log)
    log(f"Device '{name}' created.")


def _set_ram_size(name, mb, log):
    """Clamp the AVD's guest RAM so each running device stays light on host RAM."""
    ini = os.path.join(os.path.expanduser("~"), ".android", "avd",
                       f"{name}.avd", "config.ini")
    try:
        with open(ini, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        log("Warning: config.ini not found, RAM tweak skipped.")
        return
    out, seen = [], False
    for line in lines:
        if line.startswith("hw.ramSize="):
            out.append(f"hw.ramSize={mb}")
            seen = True
        else:
            out.append(line)
    if not seen:
        out.append(f"hw.ramSize={mb}")
    with open(ini, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    log(f"Device RAM limited to {mb} MB.")


def _avd_base_dir():
    return os.path.join(os.path.expanduser("~"), ".android", "avd")


def clone_avd(name, new_name, log, sdk_dir=None):
    """Duplicate a device (with its apps/data). Source device must be powered off."""
    base = _avd_base_dir()
    src_avd, src_ini = os.path.join(base, f"{name}.avd"), os.path.join(base, f"{name}.ini")
    dst_avd, dst_ini = os.path.join(base, f"{new_name}.avd"), os.path.join(base, f"{new_name}.ini")
    if not os.path.isdir(src_avd) or not os.path.isfile(src_ini):
        raise RuntimeError(f"Device '{name}' not found.")
    if os.path.exists(dst_avd) or os.path.exists(dst_ini):
        raise RuntimeError(f"A device named '{new_name}' already exists.")
    log(f"Cloning '{name}' -> '{new_name}' (make sure '{name}' is powered off)...")
    try:
        shutil.copytree(src_avd, dst_avd)
        shutil.copy2(src_ini, dst_ini)
    except Exception as e:
        shutil.rmtree(dst_avd, ignore_errors=True)
        if os.path.isfile(dst_ini):
            os.remove(dst_ini)
        raise RuntimeError(f"Clone failed (is the device still running?): {e}")
    # Point the new .ini at the new .avd directory.
    with open(dst_ini, "r", encoding="utf-8") as f:
        content = f.read().replace(f"{name}.avd", f"{new_name}.avd")
    with open(dst_ini, "w", encoding="utf-8") as f:
        f.write(content)
    # Update the device id inside config.ini.
    cfg = os.path.join(dst_avd, "config.ini")
    with open(cfg, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    out = []
    for line in lines:
        if line.startswith("avd.id="):
            out.append(f"avd.id={new_name}")
        elif line.startswith("AvdId="):
            out.append(f"AvdId={new_name}")
        else:
            out.append(line)
    with open(cfg, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    log(f"Device '{new_name}' cloned from '{name}'.")


def get_running_avds(sdk_dir=None):
    """Return {emulator_serial: avd_name} for currently running devices."""
    adb = sdk.sdk_paths(sdk_dir)["adb"]
    r = _run([adb, "devices"], capture_output=True, text=True, timeout=30)
    mapping = {}
    for line in r.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device" and parts[0].startswith("emulator-"):
            serial = parts[0]
            name = serial
            try:
                n = _run([adb, "-s", serial, "emu", "avd", "name"],
                         capture_output=True, text=True, timeout=15)
                first = next((l.strip() for l in n.stdout.splitlines() if l.strip()), "")
                if first and first.upper() != "OK":
                    name = first
            except Exception:
                pass
            mapping[serial] = name
    return mapping


def install_apk(avd_name, apk_path, log, sdk_dir=None):
    """Install an APK on a RUNNING device via adb."""
    if not os.path.isfile(apk_path):
        raise RuntimeError("APK file not found.")
    adb = sdk.sdk_paths(sdk_dir)["adb"]
    running = get_running_avds(sdk_dir)
    serial = next((s for s, n in running.items() if n == avd_name), None)
    if not serial:
        raise RuntimeError(f"Device '{avd_name}' is not running — launch it first.")
    log(f"Installing {os.path.basename(apk_path)} on '{avd_name}'...")
    r = _run([adb, "-s", serial, "install", "-r", apk_path],
             capture_output=True, text=True, timeout=300)
    log((r.stdout + r.stderr)[-2000:])
    if "Success" not in (r.stdout + r.stderr):
        raise RuntimeError("APK install failed — see the log above.")
    log("APK installed successfully.")


def delete_avd(name, sdk_dir=None):
    paths = sdk.sdk_paths(sdk_dir)
    _run([paths["avdmanager"], "delete", "avd", "-n", name],
         capture_output=True, timeout=120)


def launch_avd(name, sdk_dir=None):
    """Start the emulator detached (returns immediately)."""
    paths = sdk.sdk_paths(sdk_dir)
    DETACHED = 0x00000008  # DETACHED_PROCESS
    subprocess.Popen(
        [paths["emulator"], "-avd", name],
        creationflags=CREATE_NO_WINDOW | DETACHED,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        close_fds=True,
    )
