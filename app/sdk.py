"""Download Google's command-line tools and install SDK packages via sdkmanager."""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

from . import config

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def _run(cmd, **kwargs):
    """Run a command without popping a console window on Windows."""
    kwargs.setdefault("creationflags", CREATE_NO_WINDOW)
    return subprocess.run(cmd, **kwargs)


def sdk_paths(sdk_dir=None):
    sdk_dir = sdk_dir or config.SDK_DIR
    ct = os.path.join(sdk_dir, "cmdline-tools", "latest", "bin")
    em = os.path.join(sdk_dir, "emulator")
    pt = os.path.join(sdk_dir, "platform-tools")
    exe = ".exe" if sys.platform == "win32" else ""
    return {
        "sdk_dir": sdk_dir,
        "sdkmanager": os.path.join(ct, "sdkmanager.bat" if sys.platform == "win32" else "sdkmanager"),
        "avdmanager": os.path.join(ct, "avdmanager.bat" if sys.platform == "win32" else "avdmanager"),
        "emulator": os.path.join(em, "emulator" + exe),
        "adb": os.path.join(pt, "adb" + exe),
    }


def java_available():
    try:
        r = _run(["java", "-version"], capture_output=True, text=True, timeout=15)
        return r.returncode == 0
    except Exception:
        return False


def is_setup(sdk_dir=None):
    """True when the emulator binary is already installed."""
    return os.path.isfile(sdk_paths(sdk_dir)["emulator"])


def download_cmdline_tools(log, sdk_dir=None):
    """Download + unpack cmdline-tools into <sdk>/cmdline-tools/latest/."""
    sdk_dir = sdk_dir or config.SDK_DIR
    dest = os.path.join(sdk_dir, "cmdline-tools", "latest")
    if os.path.isfile(os.path.join(dest, "bin", "sdkmanager.bat")):
        log("command-line tools already present, skipping download.")
        return
    log(f"Downloading command-line tools...\n  {config.CMDLINE_TOOLS_URL}")
    os.makedirs(sdk_dir, exist_ok=True)
    tmp = tempfile.mkdtemp()
    zippath = os.path.join(tmp, "cmdtools.zip")
    try:
        def progress(blocks, block_size, total):
            if total > 0:
                pct = min(100, blocks * block_size * 100 // total)
                # log only at milestones to avoid spam
                if pct % 25 == 0 and getattr(progress, "last", -1) != pct:
                    progress.last = pct
                    log(f"  ... {pct}%")

        urllib.request.urlretrieve(config.CMDLINE_TOOLS_URL, zippath, progress)
        log("Unpacking...")
        with zipfile.ZipFile(zippath, "r") as z:
            z.extractall(tmp)
        # zip contains cmdline-tools/{bin,lib,...} -> move to cmdline-tools/latest/
        extracted = os.path.join(tmp, "cmdline-tools")
        if os.path.isdir(dest):
            shutil.rmtree(dest)
        shutil.move(extracted, dest)
        log("command-line tools ready.")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def install_packages(log, sdk_dir=None, retries=3):
    """Install platform-tools, emulator and the system image (auto-accept licenses).

    Retries the install a few times: the ~3-4 GB download is often aborted
    mid-way by flaky networks or antivirus/firewall software, and sdkmanager
    resumes partial downloads ("Checking existing file...") on the next run.
    """
    paths = sdk_paths(sdk_dir)
    sm = paths["sdkmanager"]
    if not os.path.isfile(sm):
        raise RuntimeError("sdkmanager not found — did the download step fail?")
    log("Installing SDK packages (this downloads ~3-4 GB, please wait)...")
    # "y" answers every license prompt.
    last_err = None
    for attempt in range(1, retries + 1):
        if attempt > 1:
            log(f"Download was interrupted — retrying ({attempt}/{retries})...")
            time.sleep(10)
        proc = _run(
            [sm, "--sdk_root=" + paths["sdk_dir"], "--install"] + config.PACKAGES,
            input="y\n" * 200,
            text=True,
            capture_output=True,
            timeout=3600,
        )
        log(proc.stdout[-3000:])
        if proc.returncode == 0:
            log("All packages installed.")
            return
        log(proc.stderr[-3000:])
        last_err = f"sdkmanager failed (exit {proc.returncode}). See log above."
    raise RuntimeError(
        last_err + f" (tried {retries} times — check your internet connection and "
        "make sure your antivirus/firewall isn't blocking the download, then run Setup again.)"
    )
