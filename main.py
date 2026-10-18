"""Android Emulator Launcher — one-click AVD setup for Windows. No Android Studio."""
import queue
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, scrolledtext, simpledialog

from app import avd, config, sdk, updater

RAM_LABELS = {1024: "1 GB", 2048: "2 GB", 4096: "4 GB"}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{config.APP_NAME} v{config.APP_VERSION}")
        self.geometry("660x560")
        self.resizable(False, False)
        self.log_q = queue.Queue()

        # Update banner (hidden until a newer release is found).
        self.update_frame = tk.Frame(self)
        self.update_label = tk.Label(self.update_frame, font=("Segoe UI", 9, "bold"),
                                     fg="#0b5fff")
        self.update_label.pack(side="left", padx=16)
        tk.Button(self.update_frame, text="Download update",
                  command=lambda: webbrowser.open(config.RELEASES_PAGE_URL)).pack(side="left")

        tk.Label(self, text=config.APP_NAME,
                 font=("Segoe UI", 16, "bold")).pack(pady=10)
        self._title_anchor = self.winfo_children()[-1]
        tk.Label(
            self,
            text="Google's official emulator — without installing Android Studio.",
            font=("Segoe UI", 9), fg="gray",
        ).pack()

        btns = tk.Frame(self)
        btns.pack(pady=10)
        tk.Button(btns, text="1. Setup (one-time download)", width=24,
                  command=self.do_setup).grid(row=0, column=0, padx=4)
        tk.Button(btns, text="2. Create device", width=16,
                  command=self.do_create).grid(row=0, column=1, padx=4)
        tk.Label(btns, text="RAM:", font=("Segoe UI", 9)).grid(row=0, column=2)
        self.ram_var = tk.StringVar(value=RAM_LABELS[config.DEVICE_RAM_MB])
        tk.OptionMenu(btns, self.ram_var,
                      *[RAM_LABELS[m] for m in config.RAM_OPTIONS_MB]).grid(row=0, column=3)

        tk.Button(btns, text="Launch", width=10,
                  command=self.do_launch).grid(row=1, column=0, padx=4, pady=4)
        tk.Button(btns, text="Launch All", width=10,
                  command=self.do_launch_all).grid(row=1, column=1, padx=4, pady=4)
        tk.Button(btns, text="Clone", width=10,
                  command=self.do_clone).grid(row=1, column=2, padx=4, pady=4)
        tk.Button(btns, text="Install APK", width=10,
                  command=self.do_install_apk).grid(row=1, column=3, padx=4, pady=4)
        tk.Button(btns, text="Delete", width=10,
                  command=self.do_delete).grid(row=1, column=4, padx=4, pady=4)

        tk.Label(self, text="Your virtual devices:", font=("Segoe UI", 9, "bold"),
                 anchor="w").pack(fill="x", padx=16)
        self.devices = tk.Listbox(self, height=4, font=("Segoe UI", 10))
        self.devices.pack(fill="x", padx=16)
        tk.Button(self, text="Refresh list", command=self.refresh).pack(pady=4)

        tk.Label(self, text="Log:", font=("Segoe UI", 9, "bold"),
                 anchor="w").pack(fill="x", padx=16)
        self.logbox = scrolledtext.ScrolledText(self, height=12, font=("Consolas", 9),
                                               state="disabled")
        self.logbox.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        self.after(200, self.pump_log)
        self.refresh(silent=True)
        self.log("Ready. Click '1. Setup' if this is your first run.")
        self.run_bg(self.check_updates)

    def check_updates(self):
        newer, latest = updater.check_for_update()
        if newer and latest:
            # Schedule UI work on the main thread (tkinter isn't thread-safe).
            self.after(0, lambda: self.show_update_banner(latest))

    def show_update_banner(self, latest):
        self.update_label.config(text=f"Update available: {latest}")
        self.update_frame.pack(fill="x", before=self._title_anchor)
        self.log(f"Update available: {latest} — click 'Download update' above.")

    # ---- logging from worker threads ----
    def log(self, msg):
        self.log_q.put(str(msg))

    def pump_log(self):
        while not self.log_q.empty():
            msg = self.log_q.get_nowait()
            self.logbox.configure(state="normal")
            self.logbox.insert("end", msg + "\n")
            self.logbox.see("end")
            self.logbox.configure(state="disabled")
        self.after(200, self.pump_log)

    def run_bg(self, fn):
        threading.Thread(target=self._wrap, args=(fn,), daemon=True).start()

    def _wrap(self, fn):
        try:
            fn()
        except Exception as e:  # noqa: BLE001 - show everything in the log
            self.log(f"ERROR: {e}")
        self.refresh(silent=True)

    def selected(self):
        sel = self.devices.curselection()
        return self.devices.get(sel[0]) if sel else None

    # ---- actions ----
    def do_setup(self):
        def job():
            if not sdk.java_available():
                self.log("ERROR: Java not found. Install Eclipse Temurin from "
                         "adoptium.net, then run Setup again.")
                return
            self.log("Step 1/2: downloading command-line tools...")
            sdk.download_cmdline_tools(self.log)
            self.log("Step 2/2: installing emulator + system image...")
            sdk.install_packages(self.log)
            self.log("Setup complete! Now click '2. Create device'.")
        self.run_bg(job)

    def do_create(self):
        if not sdk.is_setup():
            messagebox.showinfo("Setup needed", "Click '1. Setup' first.")
            return
        name = simpledialog.askstring("Create device", "Device name:",
                                      initialvalue=config.DEFAULT_AVD_NAME)
        if not name:
            return
        ram_mb = next((m for m, lbl in RAM_LABELS.items()
                       if lbl == self.ram_var.get()), config.DEVICE_RAM_MB)
        clean = name.strip().replace(" ", "_")
        self.run_bg(lambda: avd.create_avd(clean, self.log, ram_mb=ram_mb))

    def do_launch(self):
        name = self.selected()
        if not name:
            messagebox.showinfo("No device", "Select a device from the list first.")
            return
        avd.launch_avd(name)
        self.log(f"Launching '{name}'... the emulator window will appear shortly.")

    def do_launch_all(self):
        names = list(self.devices.get(0, "end"))
        if not names:
            messagebox.showinfo("No devices", "Create a device first.")
            return
        def job():
            for i, name in enumerate(names):
                avd.launch_avd(name)
                self.log(f"Launching '{name}' ({i + 1}/{len(names)})...")
                if i < len(names) - 1:
                    time.sleep(5)  # stagger so the PC isn't hammered at once
        self.run_bg(job)

    def do_clone(self):
        name = self.selected()
        if not name:
            messagebox.showinfo("No device", "Select a device from the list first.")
            return
        new_name = simpledialog.askstring("Clone device",
                                          f"Name for the copy of '{name}':",
                                          initialvalue=f"{name}_copy")
        if not new_name:
            return
        clean = new_name.strip().replace(" ", "_")
        self.run_bg(lambda: avd.clone_avd(name, clean, self.log))

    def do_install_apk(self):
        name = self.selected()
        if not name:
            messagebox.showinfo("No device", "Select a device from the list first.")
            return
        apk = filedialog.askopenfilename(title="Select APK",
                                         filetypes=[("Android APK", "*.apk")])
        if not apk:
            return
        self.run_bg(lambda: avd.install_apk(name, apk, self.log))

    def do_delete(self):
        name = self.selected()
        if not name:
            return
        if messagebox.askyesno("Delete", f"Delete virtual device '{name}'?"):
            self.run_bg(lambda: (avd.delete_avd(name),
                                 self.log(f"Deleted '{name}'.")))

    def refresh(self, silent=False):
        self.devices.delete(0, "end")
        try:
            if sdk.is_setup():
                for d in avd.list_avds():
                    self.devices.insert("end", d)
            elif not silent:
                self.log("SDK not set up yet — click '1. Setup'.")
        except Exception as e:  # noqa: BLE001
            if not silent:
                self.log(f"Could not list devices: {e}")


if __name__ == "__main__":
    App().mainloop()
