"""Android Emulator Launcher — one-click AVD setup for Windows. No Android Studio."""
import queue
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog

from app import avd, config, sdk


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{config.APP_NAME} v{config.APP_VERSION}")
        self.geometry("640x520")
        self.resizable(False, False)
        self.log_q = queue.Queue()

        tk.Label(self, text=config.APP_NAME, font=("Segoe UI", 16, "bold")).pack(pady=10)
        tk.Label(
            self,
            text="Google's official emulator — without installing Android Studio.",
            font=("Segoe UI", 9), fg="gray",
        ).pack()

        btns = tk.Frame(self)
        btns.pack(pady=10)
        tk.Button(btns, text="1. Setup (one-time download)", width=26,
                  command=self.do_setup).grid(row=0, column=0, padx=5)
        tk.Button(btns, text="2. Create device", width=18,
                  command=self.do_create).grid(row=0, column=1, padx=5)
        tk.Button(btns, text="Launch", width=12,
                  command=self.do_launch).grid(row=0, column=2, padx=5)
        tk.Button(btns, text="Delete", width=12,
                  command=self.do_delete).grid(row=0, column=3, padx=5)

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
        self.run_bg(lambda: avd.create_avd(name.strip().replace(" ", "_"), self.log))

    def do_launch(self):
        name = self.selected()
        if not name:
            messagebox.showinfo("No device", "Select a device from the list first.")
            return
        avd.launch_avd(name)
        self.log(f"Launching '{name}'... the emulator window will appear shortly.")

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
