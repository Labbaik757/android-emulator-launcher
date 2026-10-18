# Android Emulator Launcher

A free, open-source **Windows** launcher for Android emulation — no Android Studio needed.

> **What this is:** a small desktop app that downloads Google's official Android emulator +
> system images, creates virtual devices (AVDs) and launches them with one click.
> It is a **launcher/manager**, not a new emulation engine — the engine underneath is
> Google's own emulator (open-source, part of AOSP). That is the honest, shippable scope
> for a solo project: nobody needs to reimplement QEMU or the GPU translator.

## Features (v0.2.1)

- One-click Setup: downloads Google's emulator + Android 14 Play Store image (~3–4 GB, once)
- **RAM choice per device** — 1 GB / 2 GB / 4 GB when creating a device
- **Install APK** — pick any `.apk` and install it on the running device
- **Clone device** — duplicate a configured device (apps + data) for multi-account use
- **Launch All** — start every device with one click (staggered, so the PC stays responsive)
- **Auto-update check** — the app tells you when a newer release is on GitHub
- Setup self-check: clear message if the system image download didn't finish
- Launch / Delete devices, live log window

## Quick start (Windows 10/11, 64-bit)

1. Install Python 3.10+ from python.org (tick **"Add python.exe to PATH"** during install).
2. Install Java (Eclipse Temurin from adoptium.net) — required by Google's `sdkmanager`.
3. Enable virtualization in your BIOS: **Intel VT-x** or **AMD-V** (check Task Manager →
   Performance → CPU → "Virtualization: Enabled").
4. Run:
   ```bat
   pip install -r requirements.txt
   python main.py
   ```
5. In the app: **Step 1: Setup** (downloads SDK + emulator + Android image, ~3–4 GB, one time)
   → **Step 2: Create device** → **Launch**. Done.

Or build a single `.exe`: run `scripts\build_exe.bat` (no Python needed afterwards).

## Requirements

- Windows 10/11, 64-bit
- Virtualization enabled in BIOS (Intel VT-x / AMD-V)
- 8 GB RAM recommended, ~10 GB free disk
- Internet connection (first setup downloads Google's packages)

## How it works

1. Downloads Android **command-line tools** from Google (`dl.google.com`).
2. Uses `sdkmanager` to install `platform-tools`, `emulator`, and a system image
   (default: Android 14, `google_apis_playstore` x86_64 — **includes the Play Store**,
   so games/apps install normally).
3. Uses `avdmanager` to create AVDs and launches them with the `emulator` binary.
4. Hardware acceleration is automatic (WHPX on Windows 10+ when available).

## FAQ

**Is this a brand-new emulator?**
No — and any solo project claiming that would be misleading. This is a launcher/manager
around Google's official emulator. The value: zero Android Studio, one-click setup,
free and open-source.

**Does it have the Play Store?**
Yes — the default system image is `google_apis_playstore`, which ships the Play Store
(Google's own distribution channel for emulator images).

**Will it beat BlueStacks for gaming?**
Honestly, no. BlueStacks/LDPlayer have years of game-specific polish (keymapping,
macros, multi-instance). This is a free, open-source, no-ads alternative for running
Android apps on Windows.

## Project layout

```
android-emulator-launcher/
├── main.py                 # GUI entry point
├── app/
│   ├── config.py           # URLs, package list, paths
│   ├── sdk.py              # SDK download + package install
│   ├── avd.py              # AVD create/list/launch/delete/clone/APK install
│   └── updater.py          # GitHub release update checker
├── scripts/
│   └── build_exe.bat       # PyInstaller one-file build
├── .github/workflows/
│   └── build.yml           # CI: builds Windows .exe on release
├── requirements.txt
└── LICENSE                 # MIT
```

## Roadmap

- [x] Per-device RAM choice (1/2/4 GB)
- [x] APK install button
- [x] Device clone
- [x] Launch-all button
- [x] Auto-update check
- [ ] Snapshot save/load buttons
- [ ] Dark mode

## License

MIT — free for everyone, commercial use allowed. See `LICENSE`.
