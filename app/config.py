"""Shared constants: download URLs, SDK packages, paths."""
import os

APP_NAME = "Android Emulator Launcher"
APP_VERSION = "0.2.3"

# GitHub repo — used by the in-app update checker.
GITHUB_REPO = "Labbaik757/android-emulator-launcher"
RELEASES_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
RELEASES_PAGE_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"

# Default SDK location (same default Android Studio uses).
SDK_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Android", "Sdk"
)

# Google's command-line tools. The build number changes over time — if this URL
# ever 404s, open https://developer.android.com/studio, scroll to
# "Command line tools only", and copy the Windows link here.
CMDLINE_TOOLS_URL = (
    "https://dl.google.com/android/repository/"
    "commandlinetools-win-14742923_latest.zip"
)

# Packages installed on first setup. The playstore image includes the Play Store.
PACKAGES = [
    "platform-tools",
    "emulator",
    "system-images;android-34;google_apis_playstore;x86_64",
]

SYSTEM_IMAGE = "system-images;android-34;google_apis_playstore;x86_64"
DEFAULT_AVD_NAME = "Pixel_API34"
# Must match an id from `avdmanager list device`. "pixel" exists in every version.
DEVICE_PROFILE = "pixel"
# Guest RAM per virtual device, in MB. 1024 keeps each running device light on
# host RAM (fine for light apps). Use 2048+ for heavy games — but each running
# device then needs that much host RAM.
DEVICE_RAM_MB = 1024
# RAM choices offered in the GUI when creating a device.
RAM_OPTIONS_MB = [1024, 2048, 4096]
