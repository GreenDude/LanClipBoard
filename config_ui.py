from __future__ import annotations

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import yaml

import re
import subprocess
import sys
import security_services


DEFAULT_CONFIG = {
    "device": {
        "id": "auto",
        "name": "auto",
    },
    "network": {
        "port": 8000,
        "discovery": True,
        "bootstrap_peers": [],
    },
    "hotkeys": {
        "paste": ["Key.cmd", "Key.shift", "v"],
    },
    "clipboard": {
        "poll_interval_ms": 200,
    },
    "security": {
        "enabled": False,
        "key_archive": None,
        "key_password": None,
    },
    "peers": {
        "auto_accept": True,
    },
}


class MonocleConfigApp(tk.Tk):
    def __init__(self, config_path: str = "config/config.yaml") -> None:
        super().__init__()
        self.title("Monocle Configurator")
        self.geometry("760x720")
        self.minsize(700, 640)

        self.config_path_var = tk.StringVar(value=config_path)
        self.status_var = tk.StringVar(value="Ready")

        self.device_id_var = tk.StringVar()
        self.device_name_var = tk.StringVar()

        self.network_port_var = tk.StringVar()
        self.network_discovery_var = tk.BooleanVar(value=True)
        self.bootstrap_peers_var = tk.StringVar()

        self.hotkey_paste_var = tk.StringVar()
        self.clipboard_poll_ms_var = tk.StringVar()

        self.security_enabled_var = tk.BooleanVar(value=False)
        self.security_key_archive_var = tk.StringVar()
        self.security_key_password_var = tk.StringVar()

        self.peers_auto_accept_var = tk.BooleanVar(value=True)

        self.generate_key_name_var = tk.StringVar()
        self.generate_key_password_var = tk.StringVar()

        self.server_status_var = tk.StringVar(value="Stopped")
        self.server_process = None

        self._build_ui()
        self.load_from_path(initial=True)

    def _get_config_dir(self) -> Path:
        return Path(self.config_path_var.get()).resolve().parent

    def _sanitize_key_name(self, key_name: str) -> str:
        sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", key_name.strip())
        return sanitized.strip("._")

    def generate_new_key(self) -> None:
        key_name = self._sanitize_key_name(self.generate_key_name_var.get())
        key_password = self.generate_key_password_var.get()

        if not key_name:
            messagebox.showerror("Invalid input", "Key name is required.")
            return

        if not key_password:
            messagebox.showerror("Invalid input", "Key password is required.")
            return

        config_dir = self._get_config_dir()
        private_key_path = config_dir / f"{key_name}_private.pem"
        public_key_path = config_dir / f"{key_name}_public.pem"
        archive_path = config_dir / f"{key_name}.ska"

        try:
            private_key, public_key = security_services.generate_key_pair(
                password=key_password.encode("utf-8")
            )

            private_key_path.write_bytes(private_key)
            public_key_path.write_bytes(public_key)

            security_services.package_keys(
                private_key=private_key,
                public_key=public_key,
                archive_path=archive_path,
                private_key_name=private_key_path.name,
                public_key_name=public_key_path.name,
                archive_password=key_password.encode("utf-8"),
            )

            self.security_enabled_var.set(True)
            self.security_key_archive_var.set(str(archive_path))
            self.security_key_password_var.set(key_password)

            self.save_config()
            self.status_var.set(f"Generated key archive: {archive_path}")
            messagebox.showinfo(
                "Success",
                f"Generated and packaged key pair:\n{archive_path}"
            )

        except Exception as exc:
            messagebox.showerror("Key generation failed", f"Failed to generate key pair:\n{exc}")
            self.status_var.set("Key generation failed")

    def import_key_archive(self) -> None:
        if not self.security_enabled_var.get():
            messagebox.showerror("Security disabled", "Enable security before importing a key archive.")
            return

        archive_path = self.security_key_archive_var.get().strip()
        key_password = self.security_key_password_var.get()

        if not archive_path:
            messagebox.showerror("Missing archive", "Select a key archive first.")
            return

        if not key_password:
            messagebox.showerror("Missing password", "Enter the key password.")
            return

        config_dir = self._get_config_dir()

        try:
            extracted_files = security_services.unpack_keys(
                archive_path=archive_path,
                destination_dir=config_dir,
                archive_password=key_password.encode("utf-8"),
            )

            private_key_file = next(
                (p for p in extracted_files if p.name.endswith("_private.pem") or p.name == "private_key.pem"), None)
            public_key_file = next(
                (p for p in extracted_files if p.name.endswith("_public.pem") or p.name == "public_key.pem"), None)

            if private_key_file is None or public_key_file is None:
                raise ValueError("Archive does not contain both private and public key files.")

            private_key_bytes = private_key_file.read_bytes()
            public_key_bytes = public_key_file.read_bytes()

            if not security_services.check_key_pair(
                    private_key_bytes,
                    public_key_bytes,
                    key_password.encode("utf-8"),
            ):
                raise ValueError("Imported private/public keys do not match or password is invalid.")

            self.save_config()
            self.status_var.set(f"Imported key archive: {archive_path}")
            messagebox.showinfo(
                "Success",
                f"Key archive imported successfully.\nFiles extracted to:\n{config_dir}"
            )

        except Exception as exc:
            messagebox.showerror("Import failed", f"Failed to import key archive:\n{exc}")
            self.status_var.set("Key import failed")

    def start_application(self) -> None:
        if self.server_process is not None and self.server_process.poll() is None:
            messagebox.showinfo("Already running", "The application is already running.")
            self.server_status_var.set("Running")
            return

        try:
            config_data = self._collect_config()
        except ValueError as exc:
            messagebox.showerror("Invalid config", str(exc))
            self.server_status_var.set("Stopped")
            return

        path = Path(self.config_path_var.get())
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                yaml.safe_dump(config_data, f, sort_keys=False, allow_unicode=True)
        except Exception as exc:
            messagebox.showerror("Save failed", f"Failed to save config before start:\n{exc}")
            self.server_status_var.set("Stopped")
            return

        port = config_data["network"]["port"]

        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(port),
        ]

        try:
            self.server_process = subprocess.Popen(
                cmd,
                cwd=str(Path(self.config_path_var.get()).resolve().parent.parent),
            )
            self.server_status_var.set(f"Running on port {port}")
            self.status_var.set("Application started")
        except Exception as exc:
            messagebox.showerror("Start failed", f"Failed to start application:\n{exc}")
            self.server_status_var.set("Stopped")
            self.status_var.set("Application start failed")

    def stop_application(self) -> None:
        if self.server_process is None or self.server_process.poll() is not None:
            self.server_status_var.set("Stopped")
            messagebox.showinfo("Not running", "The application is not running.")
            return

        try:
            self.server_process.terminate()
            self.server_process.wait(timeout=5)
            self.server_status_var.set("Stopped")
            self.status_var.set("Application stopped")
        except Exception as exc:
            messagebox.showerror("Stop failed", f"Failed to stop application:\n{exc}")
            self.status_var.set("Application stop failed")

    def _on_close(self) -> None:
        if self.server_process is not None and self.server_process.poll() is None:
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=3)
            except Exception:
                pass
        self.destroy()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        outer = ttk.Frame(self, padding=12)
        outer.grid(sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        path_frame = ttk.LabelFrame(outer, text="Config file", padding=10)
        path_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        path_frame.columnconfigure(1, weight=1)

        ttk.Label(path_frame, text="Path").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(path_frame, textvariable=self.config_path_var).grid(row=0, column=1, sticky="ew")
        ttk.Button(path_frame, text="Browse", command=self._browse_config).grid(row=0, column=2, padx=(8, 0))
        ttk.Button(path_frame, text="Load", command=self.load_from_path).grid(row=0, column=3, padx=(8, 0))

        notebook = ttk.Notebook(outer)
        notebook.grid(row=1, column=0, sticky="nsew")

        notebook.add(self._build_general_tab(notebook), text="General")
        notebook.add(self._build_network_tab(notebook), text="Network")
        notebook.add(self._build_hotkeys_tab(notebook), text="Hotkeys")
        notebook.add(self._build_clipboard_tab(notebook), text="Clipboard")
        notebook.add(self._build_security_tab(notebook), text="Security")
        notebook.add(self._build_peers_tab(notebook), text="Peers")

        button_bar = ttk.Frame(outer)
        button_bar.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        button_bar.columnconfigure(0, weight=1)

        ttk.Label(button_bar, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        ttk.Button(button_bar, text="Reset to defaults", command=self.reset_defaults).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(button_bar, text="Save", command=self.save_config).grid(row=0, column=2, padx=(8, 0))

    def _build_general_tab(self, parent: ttk.Notebook) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=14)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Device ID").grid(row=0, column=0, sticky="w", pady=6, padx=(0, 12))
        ttk.Entry(frame, textvariable=self.device_id_var).grid(row=0, column=1, sticky="ew", pady=6)

        ttk.Label(frame, text="Device name").grid(row=1, column=0, sticky="w", pady=6, padx=(0, 12))
        ttk.Entry(frame, textvariable=self.device_name_var).grid(row=1, column=1, sticky="ew", pady=6)

        ttk.Label(
            frame,
            text='Use "auto" to let the app derive the value automatically.',
            foreground="#666666",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 16))

        runtime_section = ttk.LabelFrame(frame, text="Application control", padding=12)
        runtime_section.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        runtime_section.columnconfigure(1, weight=1)

        ttk.Label(runtime_section, text="Status").grid(row=0, column=0, sticky="w", padx=(0, 12), pady=6)
        ttk.Label(runtime_section, textvariable=self.server_status_var).grid(row=0, column=1, sticky="w", pady=6)

        controls = ttk.Frame(runtime_section)
        controls.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

        ttk.Button(controls, text="Start", command=self.start_application).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(controls, text="Stop", command=self.stop_application).grid(row=0, column=1)

        ttk.Label(
            runtime_section,
            text="Starts uvicorn using the current config file.",
            foreground="#666666",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 0))

        return frame

    def _build_network_tab(self, parent: ttk.Notebook) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=14)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Port").grid(row=0, column=0, sticky="w", pady=6, padx=(0, 12))
        ttk.Entry(frame, textvariable=self.network_port_var).grid(row=0, column=1, sticky="ew", pady=6)

        ttk.Checkbutton(frame, text="Enable discovery", variable=self.network_discovery_var).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=6
        )

        ttk.Label(frame, text="Bootstrap peers").grid(row=2, column=0, sticky="nw", pady=6, padx=(0, 12))
        peers_text = (
            "Enter one IP or host per line.\n"
            "Leave empty to rely only on service discovery."
        )
        ttk.Label(frame, text=peers_text, foreground="#666666").grid(row=2, column=1, sticky="w", pady=(6, 4))
        ttk.Label(frame, text="Peers list").grid(row=3, column=0, sticky="nw", padx=(0, 12))
        tk.Text
        self.bootstrap_text = tk.Text(frame, height=10, width=40, wrap="word")
        self.bootstrap_text.grid(row=3, column=1, sticky="nsew")
        frame.rowconfigure(3, weight=1)

        return frame

    def _build_hotkeys_tab(self, parent: ttk.Notebook) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=14)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Paste hotkey").grid(row=0, column=0, sticky="w", pady=6, padx=(0, 12))
        ttk.Entry(frame, textvariable=self.hotkey_paste_var).grid(row=0, column=1, sticky="ew", pady=6)

        ttk.Label(
            frame,
            text="Comma-separated values, e.g. Key.cmd, Key.shift, v",
            foreground="#666666",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        return frame

    def _build_clipboard_tab(self, parent: ttk.Notebook) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=14)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Poll interval (ms)").grid(row=0, column=0, sticky="w", pady=6, padx=(0, 12))
        ttk.Entry(frame, textvariable=self.clipboard_poll_ms_var).grid(row=0, column=1, sticky="ew", pady=6)

        return frame

    def _build_security_tab(self, parent: ttk.Notebook) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=14)
        frame.columnconfigure(0, weight=1)

        import_section = ttk.LabelFrame(frame, text="Import existing key", padding=12)
        import_section.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        import_section.columnconfigure(1, weight=1)

        ttk.Checkbutton(
            import_section,
            text="Enable security",
            variable=self.security_enabled_var,
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=6)

        ttk.Label(import_section, text="Key archive").grid(row=1, column=0, sticky="w", pady=6, padx=(0, 12))
        ttk.Entry(import_section, textvariable=self.security_key_archive_var).grid(row=1, column=1, sticky="ew", pady=6)
        ttk.Button(import_section, text="Browse", command=self._browse_key_archive).grid(row=1, column=2, padx=(8, 0))

        ttk.Label(import_section, text="Key password").grid(row=2, column=0, sticky="w", pady=6, padx=(0, 12))
        ttk.Entry(import_section, textvariable=self.security_key_password_var, show="*").grid(row=2, column=1,
                                                                                              sticky="ew", pady=6)

        ttk.Button(import_section, text="Import key", command=self.import_key_archive).grid(
            row=3, column=1, sticky="e", pady=(10, 0)
        )

        generate_section = ttk.LabelFrame(frame, text="Generate new key", padding=12)
        generate_section.grid(row=1, column=0, sticky="ew")
        generate_section.columnconfigure(1, weight=1)

        ttk.Label(generate_section, text="Key name").grid(row=0, column=0, sticky="w", pady=6, padx=(0, 12))
        ttk.Entry(generate_section, textvariable=self.generate_key_name_var).grid(row=0, column=1, sticky="ew", pady=6)

        ttk.Label(generate_section, text="Key password").grid(row=1, column=0, sticky="w", pady=6, padx=(0, 12))
        ttk.Entry(generate_section, textvariable=self.generate_key_password_var, show="*").grid(
            row=1, column=1, sticky="ew", pady=6
        )

        ttk.Button(generate_section, text="Generate", command=self.generate_new_key).grid(
            row=2, column=1, sticky="e", pady=(10, 0)
        )

        return frame


    def _build_peers_tab(self, parent: ttk.Notebook) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=14)
        frame.columnconfigure(0, weight=1)

        ttk.Checkbutton(frame, text="Auto-accept peers", variable=self.peers_auto_accept_var).grid(
            row=0, column=0, sticky="w", pady=6
        )

        return frame

    def _browse_config(self) -> None:
        selected = filedialog.asksaveasfilename(
            title="Select config file",
            defaultextension=".yaml",
            filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*.*")],
            initialfile=Path(self.config_path_var.get()).name,
        )
        if selected:
            self.config_path_var.set(selected)

    def _browse_key_archive(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select key archive",
            filetypes=[("Secure key archives", "*.ska"), ("All files", "*.*")],
        )
        if selected:
            self.security_key_archive_var.set(selected)

    def _set_bootstrap_peers(self, peers: list[str]) -> None:
        self.bootstrap_text.delete("1.0", tk.END)
        if peers:
            self.bootstrap_text.insert("1.0", "\n".join(peers))

    def _get_bootstrap_peers(self) -> list[str]:
        raw = self.bootstrap_text.get("1.0", tk.END)
        return [line.strip() for line in raw.splitlines() if line.strip()]

    def reset_defaults(self) -> None:
        self._load_into_form(DEFAULT_CONFIG)
        self.status_var.set("Reset to defaults")

    def load_from_path(self, initial: bool = False) -> None:
        path = Path(self.config_path_var.get())
        if not path.exists():
            self._load_into_form(DEFAULT_CONFIG)
            if initial:
                self.status_var.set(f"Config not found, loaded defaults: {path}")
            else:
                messagebox.showwarning("Config not found", f"Config not found:\n{path}\n\nLoaded defaults instead.")
                self.status_var.set(f"Config not found, loaded defaults: {path}")
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception as exc:
            messagebox.showerror("Load failed", f"Failed to load config:\n{exc}")
            self.status_var.set("Load failed")
            return

        merged = self._merge_with_defaults(data)
        self._load_into_form(merged)
        self.status_var.set(f"Loaded {path}")

    def _merge_with_defaults(self, data: dict) -> dict:
        merged = {
            "device": dict(DEFAULT_CONFIG["device"]),
            "network": dict(DEFAULT_CONFIG["network"]),
            "hotkeys": dict(DEFAULT_CONFIG["hotkeys"]),
            "clipboard": dict(DEFAULT_CONFIG["clipboard"]),
            "security": dict(DEFAULT_CONFIG["security"]),
            "peers": dict(DEFAULT_CONFIG["peers"]),
        }

        for section, default_values in merged.items():
            incoming = data.get(section, {})
            if isinstance(incoming, dict):
                default_values.update(incoming)

        return merged

    def _load_into_form(self, data: dict) -> None:
        self.device_id_var.set(data["device"].get("id", "auto"))
        self.device_name_var.set(data["device"].get("name", "auto"))

        self.network_port_var.set(str(data["network"].get("port", 8000)))
        self.network_discovery_var.set(bool(data["network"].get("discovery", True)))
        self._set_bootstrap_peers(data["network"].get("bootstrap_peers", []))

        self.hotkey_paste_var.set(
            ", ".join(data["hotkeys"].get("paste", ["Key.cmd", "Key.shift", "v"]))
        )
        self.clipboard_poll_ms_var.set(str(data["clipboard"].get("poll_interval_ms", 200)))

        self.security_enabled_var.set(bool(data["security"].get("enabled", False)))
        self.security_key_archive_var.set(data["security"].get("key_archive") or "")
        self.security_key_password_var.set(data["security"].get("key_password") or "")

        self.peers_auto_accept_var.set(bool(data["peers"].get("auto_accept", True)))

    def _collect_config(self) -> dict:
        try:
            port = int(self.network_port_var.get().strip())
        except ValueError as exc:
            raise ValueError("Network port must be an integer") from exc

        try:
            poll_interval = int(self.clipboard_poll_ms_var.get().strip())
        except ValueError as exc:
            raise ValueError("Clipboard poll interval must be an integer") from exc

        hotkey_parts = [part.strip() for part in self.hotkey_paste_var.get().split(",") if part.strip()]
        if not hotkey_parts:
            raise ValueError("Paste hotkey cannot be empty")

        key_archive = self.security_key_archive_var.get().strip() or None
        key_password = self.security_key_password_var.get() or None

        return {
            "device": {
                "id": self.device_id_var.get().strip() or "auto",
                "name": self.device_name_var.get().strip() or "auto",
            },
            "network": {
                "port": port,
                "discovery": self.network_discovery_var.get(),
                "bootstrap_peers": self._get_bootstrap_peers(),
            },
            "hotkeys": {
                "paste": hotkey_parts,
            },
            "clipboard": {
                "poll_interval_ms": poll_interval,
            },
            "security": {
                "enabled": self.security_enabled_var.get(),
                "key_archive": key_archive,
                "key_password": key_password,
            },
            "peers": {
                "auto_accept": self.peers_auto_accept_var.get(),
            },
        }

    def save_config(self) -> None:
        try:
            config_data = self._collect_config()
        except ValueError as exc:
            messagebox.showerror("Invalid config", str(exc))
            self.status_var.set("Validation failed")
            return

        path = Path(self.config_path_var.get())
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                yaml.safe_dump(config_data, f, sort_keys=False, allow_unicode=True)
        except Exception as exc:
            messagebox.showerror("Save failed", f"Failed to save config:\n{exc}")
            self.status_var.set("Save failed")
            return

        self.status_var.set(f"Saved {path}")
        messagebox.showinfo("Saved", f"Configuration saved to:\n{path}")


if __name__ == "__main__":
    app = MonocleConfigApp()
    app.mainloop()
