"""Create / list / launch / delete / clone Android Virtual Devices."""
import os
import re
import shutil
import subprocess
import sys

from . import config, sdk

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def _run(cmd, sdk_dir=None, **kwargs):
    kwargs.setdefault("creationflags", CREATE_NO_WINDOW)
    # Pin the SDK location for every child process: avdmanager resolves its
    # SDK root on its own when not given --sdk_root, so a stale ANDROID_HOME /
    # ANDROID_SDK_ROOT on the user's PC can make it scan a different,
    # image-less SDK directory -- surfacing as "Error: Package path is not
    # valid. Valid system image paths are: null". Forcing the variables
    # removes that whole failure class.
    env = dict(kwargs.pop("env", None) or os.environ)
    root = sdk.sdk_paths(sdk_dir)["sdk_dir"]
    env["ANDROID_HOME"] = root
    env["ANDROID_SDK_ROOT"] = root
    kwargs["env"] = env
    return subprocess.run(cmd, **kwargs)


def list_avds(sdk_dir=None):
    paths = sdk.sdk_paths(sdk_dir)
    r = _run([paths["emulator"], "-list-avds"], sdk_dir=sdk_dir,
             capture_output=True, text=True, timeout=60)
    return [l.strip() for l in r.stdout.splitlines() if l.strip()]


def list_device_profiles(sdk_dir=None):
    """Return [(id, name, oem), ...] of hardware profiles from `avdmanager list device`."""
    paths = sdk.sdk_paths(sdk_dir)
    r = _run([paths["avdmanager"], "list", "device"],
             sdk_dir=sdk_dir, capture_output=True, text=True, timeout=60)
    profiles, cur = [], {}
    for raw in r.stdout.splitlines():
        line = raw.strip()
        if line.startswith("id:"):
            m = re.search(r'"([^"]+)"', line)
            if m:
                if cur.get("id"):
                    profiles.append(cur)
                cur = {"id": m.group(1), "name": "", "oem": ""}
        elif line.startswith("Name:"):
            cur["name"] = line.split("Name:", 1)[1].strip()
        elif line.startswith("OEM"):
            cur["oem"] = line.split(":", 1)[1].strip()
        elif line.startswith("---"):
            if cur.get("id"):
                profiles.append(cur)
                cur = {}
    if cur.get("id"):
        profiles.append(cur)
    return [(p["id"], p.get("name") or p["id"], p.get("oem") or "") for p in profiles]


def _image_install_dir(sdk_dir=None):
    # "system-images;android-34;google_apis_playstore;x86_64" -> path parts
    parts = config.SYSTEM_IMAGE.split(";")
    return os.path.join(sdk.sdk_paths(sdk_dir)["sdk_dir"], *parts)


def system_image_installed(sdk_dir=None):
    # Both files must exist: a download interrupted mid-way can leave
    # package.xml behind without the actual system.img.
    d = _image_install_dir(sdk_dir)
    return (os.path.isfile(os.path.join(d, "package.xml"))
            and os.path.isfile(os.path.join(d, "system.img")))


def create_avd(name, log, sdk_dir=None, ram_mb=None, device_profile=None):
    # Self-heal: package.xml without system.img means an interrupted download.
    # Remove it so the next Setup re-downloads the image cleanly instead of
    # avdmanager failing cryptically on a half-present image.
    img_dir = _image_install_dir(sdk_dir)
    if (os.path.isfile(os.path.join(img_dir, "package.xml"))
            and not os.path.isfile(os.path.join(img_dir, "system.img"))):
        log("Incomplete system image found -- removing it so Setup can re-download...")
        shutil.rmtree(img_dir, ignore_errors=True)
    if not system_image_installed(sdk_dir):
        raise RuntimeError(
            "System image is not installed — the Setup download didn't finish. "
            "Click '1. Setup' again and wait for 'All packages installed.' in the log."
        )
    paths = sdk.sdk_paths(sdk_dir)
    log(f"Creating virtual device '{name}'...")
    # "no" = don't use a custom hardware profile.
    # --sdk_root is passed explicitly: without it avdmanager resolves the SDK
    # root on its own and may scan an image-less directory ("Valid system
    # image paths are: null"). NOTE: avdmanager only accepts it AFTER the verb
    # ("create avd --sdk_root=...") — as a global flag it fails with
    # "not a valid global flag".
    avd_args = [
        paths["avdmanager"],
        "create", "avd",
        "--sdk_root=" + paths["sdk_dir"],
        "-n", name,
        "-k", config.SYSTEM_IMAGE,
        "-d", device_profile or config.DEVICE_PROFILE,
        "--force",
    ]
    r = _run(avd_args, sdk_dir=sdk_dir, input="no\n",
             text=True, capture_output=True, timeout=600)
    out = r.stdout + r.stderr
    if r.returncode != 0 and "--sdk_root" in out and "not a valid" in out:
        # Some avdmanager builds reject --sdk_root entirely; retry without it.
        # ANDROID_HOME/ANDROID_SDK_ROOT are pinned by _run, which is enough on
        # its own to point at the right SDK directory.
        log("avdmanager rejected --sdk_root; retrying without it...")
        avd_args = [a for a in avd_args if not a.startswith("--sdk_root")]
        r = _run(avd_args, sdk_dir=sdk_dir, input="no\n",
                 text=True, capture_output=True, timeout=600)
        out = r.stdout + r.stderr
    log(out[-2000:])
    if r.returncode != 0:
        # Self-diagnosing details: which SDK root avdmanager actually used
        # and what images were visible there.
        try:
            seen = sorted(os.listdir(os.path.join(paths["sdk_dir"], "system-images")))
        except OSError:
            seen = []
        log(f"SDK root used: {paths['sdk_dir']}")
        log(f"System images visible there: {seen if seen else 'NONE'}")
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
    r = _run([adb, "devices"], sdk_dir=sdk_dir, capture_output=True, text=True, timeout=30)
    mapping = {}
    for line in r.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device" and parts[0].startswith("emulator-"):
            serial = parts[0]
            name = serial
            try:
                n = _run([adb, "-s", serial, "emu", "avd", "name"],
                         sdk_dir=sdk_dir, capture_output=True, text=True, timeout=15)
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
             sdk_dir=sdk_dir, capture_output=True, text=True, timeout=300)
    log((r.stdout + r.stderr)[-2000:])
    if "Success" not in (r.stdout + r.stderr):
        raise RuntimeError("APK install failed — see the log above.")
    log("APK installed successfully.")


def delete_avd(name, sdk_dir=None):
    paths = sdk.sdk_paths(sdk_dir)
    _run([paths["avdmanager"],
          "delete", "avd",
          "--sdk_root=" + paths["sdk_dir"],
          "-n", name],
         sdk_dir=sdk_dir, capture_output=True, timeout=120)


def launch_avd(name, sdk_dir=None):
    """Start the emulator detached (returns immediately)."""
    paths = sdk.sdk_paths(sdk_dir)
    DETACHED = 0x00000008  # DETACHED_PROCESS
    # Pin the SDK location like _run does, so the emulator never resolves
    # a different SDK root from a stale environment.
    env = dict(os.environ)
    env["ANDROID_HOME"] = paths["sdk_dir"]
    env["ANDROID_SDK_ROOT"] = paths["sdk_dir"]
    subprocess.Popen(
        [paths["emulator"], "-avd", name],
        creationflags=CREATE_NO_WINDOW | DETACHED,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        close_fds=True,
        env=env,
    )
