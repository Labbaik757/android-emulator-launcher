"""Create / list / launch / delete Android Virtual Devices."""
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


def create_avd(name, log, sdk_dir=None):
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
    log(f"Device '{name}' created.")


def delete_avd(name, sdk_dir=None):
    paths = sdk.sdk_paths(sdk_dir)
    _run([paths["avdmanager"], "delete", "avd", "-n", name],
         capture_output=True, timeout=120)


def launch_avd(name, sdk_dir=None):
    """Start the emulator detached (returns immediately)."""
    paths = sdk.sdk_paths(sdk_dir)
    DETACHED = 0x00000008 # DETACHED_PROCESS
    subprocess.Popen(
        [paths["emulator"], "-avd", name],
        creationflags=CREATE_NO_WINDOW | DETACHED,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        close_fds=True,
)
