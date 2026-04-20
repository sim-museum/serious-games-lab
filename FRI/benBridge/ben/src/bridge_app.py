"""Q-Plus style front-end for BEN.

Top-level menubar:
  File  -> Exit
  Server -> Start local bridge server...
          -> Connect to local bridge server...
  Help  -> About

Without using the Server menu, selecting nothing activates the multi-human
mode: the app simply runs as a normal BEN launcher.  The multi-human flow
is triggered exclusively by the two Server menu commands, mirroring
Q-plus Bridge's "Network" menu behaviour.
"""

import os
import sys
import json
import queue
import signal
import socket
import threading
import subprocess
import time
import webbrowser

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

env = os.environ.copy()
env["PYTHONIOENCODING"] = "utf-8"
env["BEN_HOME"] = "."

SEAT_ORDER = ['North', 'East', 'South', 'West']
SEAT_LETTER = {'North': 'N', 'East': 'E', 'South': 'S', 'West': 'W'}

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bridge_app.settings.json")


def load_settings():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_settings(settings):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(settings, f, indent=2)
    except Exception as ex:
        print(f"Could not save settings: {ex}")


def get_local_ips():
    ips = ['127.0.0.1']
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None):
            ip = info[4][0]
            if ip not in ips and not ip.startswith('::'):
                ips.append(ip)
    except Exception:
        pass
    return ips


class ServerProcess:
    """Runs gameserver.py as a subprocess and streams output into a queue."""

    def __init__(self, log_callback):
        self.proc = None
        self.log = log_callback
        self._reader_threads = []

    def start(self, port, config=None, boards=None, matchpoint=False, verbose=False):
        if self.proc is not None:
            self.log("Server already running.\n", "red")
            return False

        script_dir = os.path.dirname(os.path.abspath(__file__))
        exe_path = os.path.join(script_dir, 'gameserver.exe')
        if os.path.exists(exe_path):
            cmd = [exe_path]
        else:
            cmd = [sys.executable, os.path.join(script_dir, 'gameserver.py')]

        cmd.extend(['--port', str(port)])
        if config:
            cmd.extend(['--config', config])
        if boards:
            cmd.extend(['--boards', boards])
        if matchpoint:
            cmd.extend(['--matchpoint', 'True'])
        if verbose:
            cmd.extend(['--verbose', 'True'])

        creation_flags = 0
        if sys.platform == 'win32':
            creation_flags = subprocess.CREATE_NO_WINDOW

        try:
            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=script_dir,
                env=env,
                creationflags=creation_flags,
            )
        except Exception as ex:
            self.log(f"Failed to start server: {ex}\n", "red")
            return False

        def reader(stream, color):
            try:
                for line in iter(stream.readline, b''):
                    if not line:
                        break
                    try:
                        self.log(line.decode('utf-8', errors='replace'), color)
                    except Exception:
                        pass
            except Exception:
                pass

        t1 = threading.Thread(target=reader, args=(self.proc.stdout, 'green'), daemon=True)
        t2 = threading.Thread(target=reader, args=(self.proc.stderr, 'yellow'), daemon=True)
        t1.start()
        t2.start()
        self._reader_threads = [t1, t2]

        self.log(f"< I > Server started on port {port}, waiting for TCP/IP connections ...\n", "green")
        for ip in get_local_ips():
            self.log(f"< I > IP Addr = {ip}\n", "green")
        return True

    def stop(self):
        if self.proc is None:
            return
        try:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        except Exception as ex:
            self.log(f"Error stopping server: {ex}\n", "red")
        self.proc = None
        self.log("< I > Server stopped.\n", "yellow")

    def is_running(self):
        return self.proc is not None and self.proc.poll() is None


class LocalServerDialog(tk.Toplevel):
    """Q-Plus-style 'Local bridge server' dialog."""

    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.title("Local bridge server")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        settings = app.settings
        self.seat_names = {s: tk.StringVar(value=settings.get(f"seat_{s}_name", s)) for s in SEAT_ORDER}
        self.local_seat = tk.StringVar(value=settings.get("local_seat", "South"))
        self.port_var = tk.StringVar(value=str(settings.get("port", 4443)))

        self._build_ui()
        self._refresh_conn_labels()

        # Update conn labels periodically
        self.after(1000, self._tick)

    def _build_ui(self):
        pad = {'padx': 6, 'pady': 3}

        # Players frame
        players_frame = ttk.LabelFrame(self, text="Players")
        players_frame.grid(row=0, column=0, padx=8, pady=8, sticky="nsew")

        self.conn_labels = {}
        for i, seat in enumerate(SEAT_ORDER):
            ttk.Label(players_frame, text=f"{seat}:").grid(row=i, column=0, sticky="w", **pad)
            ttk.Entry(players_frame, textvariable=self.seat_names[seat], width=14).grid(row=i, column=1, **pad)
            lab = ttk.Label(players_frame, text="not conn.", width=10)
            lab.grid(row=i, column=2, sticky="w", **pad)
            self.conn_labels[seat] = lab

        # Local seat frame (which seat the local user plays)
        local_frame = ttk.LabelFrame(self, text="Local")
        local_frame.grid(row=0, column=1, padx=8, pady=8, sticky="nsew")
        for i, seat in enumerate(SEAT_ORDER):
            ttk.Radiobutton(local_frame, text=seat, value=seat, variable=self.local_seat).grid(
                row=i, column=0, sticky="w", **pad)

        # Server frame
        server_frame = ttk.LabelFrame(self, text="Server")
        server_frame.grid(row=1, column=0, columnspan=2, padx=8, pady=8, sticky="nsew")
        ttk.Label(server_frame, text="Port:").grid(row=0, column=0, **pad)
        ttk.Entry(server_frame, textvariable=self.port_var, width=8).grid(row=0, column=1, **pad)
        self.start_btn = ttk.Button(server_frame, text="Start", command=self.on_start)
        self.start_btn.grid(row=0, column=2, **pad)
        self.stop_btn = ttk.Button(server_frame, text="Stop", command=self.on_stop, state="disabled")
        self.stop_btn.grid(row=0, column=3, **pad)

        # Messages
        msg_frame = ttk.LabelFrame(self, text="Messages")
        msg_frame.grid(row=2, column=0, columnspan=2, padx=8, pady=8, sticky="nsew")
        self.msg_text = tk.Text(msg_frame, width=70, height=10, state="disabled", bg="#101820", fg="white")
        self.msg_text.pack(side="left", fill="both", expand=True)
        self.msg_text.tag_configure("red", foreground="#FF7F50")
        self.msg_text.tag_configure("green", foreground="#90EE90")
        self.msg_text.tag_configure("yellow", foreground="#FFD700")
        sb = ttk.Scrollbar(msg_frame, orient="vertical", command=self.msg_text.yview)
        self.msg_text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

        # Footer buttons
        foot = ttk.Frame(self)
        foot.grid(row=3, column=0, columnspan=2, padx=8, pady=(0, 8), sticky="ew")
        ttk.Button(foot, text="Open local browser", command=self.open_local_browser).pack(side="left")
        ttk.Button(foot, text="Close", command=self.on_close).pack(side="right")
        ttk.Button(foot, text="Help", command=self.show_help).pack(side="right", padx=(0, 6))

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def log(self, text, color=None):
        def _inner():
            self.msg_text.configure(state="normal")
            if color:
                self.msg_text.insert("end", text, color)
            else:
                self.msg_text.insert("end", text)
            self.msg_text.configure(state="disabled")
            self.msg_text.see("end")
        try:
            self.after(0, _inner)
        except Exception:
            pass

    def _tick(self):
        # Keep refreshing in case future reconnection logic is wired in.
        self._refresh_conn_labels()
        self.after(2000, self._tick)

    def _refresh_conn_labels(self):
        # We don't have a live channel from the server to the GUI yet; show
        # the local seat as "Local" and the rest as "not conn." / "Bot".
        local = self.local_seat.get()
        for seat in SEAT_ORDER:
            if seat == local:
                self.conn_labels[seat].configure(text="Local")
            else:
                self.conn_labels[seat].configure(text="not conn.")

    def on_start(self):
        port = self.port_var.get().strip()
        try:
            port_i = int(port)
        except ValueError:
            messagebox.showerror("Invalid port", "Port must be an integer.")
            return

        # Persist settings
        self.app.settings["port"] = port_i
        self.app.settings["local_seat"] = self.local_seat.get()
        for seat in SEAT_ORDER:
            self.app.settings[f"seat_{seat}_name"] = self.seat_names[seat].get()
        save_settings(self.app.settings)

        ok = self.app.server.start(port=port_i, verbose=False)
        if ok:
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")

    def on_stop(self):
        self.app.server.stop()
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    def open_local_browser(self):
        port = self.port_var.get().strip() or "4443"
        seat = self.local_seat.get()
        letter = SEAT_LETTER[seat]
        table_id = self.app.settings.get("table_id", "local1")
        # Point at the existing frontend that the project already ships.
        # It expects to proxy websockets to ws://host:port/.
        url = (
            f"http://localhost:8080/app/bridge.html?"
            f"{letter}=x&table={table_id}&seat={letter}&name={self.seat_names[seat].get()}&server=localhost:{port}"
        )
        try:
            webbrowser.open(url)
            self.log(f"Opened browser: {url}\n", "green")
        except Exception as ex:
            self.log(f"Could not open browser: {ex}\n", "red")

    def show_help(self):
        messagebox.showinfo(
            "Local bridge server — Help",
            "Start the server on a chosen port, then share the host/port with other\n"
            "players (or open another browser locally).\n\n"
            "Each remote client uses 'Connect to local bridge server…' and picks a\n"
            "seat. The first client to connect configures the table; empty seats\n"
            "are filled by BEN bots.\n\n"
            "The 'Local' radio selects which seat THIS machine's browser plays."
        )

    def on_close(self):
        if self.app.server.is_running():
            if not messagebox.askyesno("Stop server?", "Server is running. Stop it and close?"):
                return
            self.on_stop()
        self.destroy()


class ConnectDialog(tk.Toplevel):
    """Dialog to connect to a remote bridge server."""

    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.title("Connect to local bridge server")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        settings = app.settings
        self.host_var = tk.StringVar(value=settings.get("connect_host", "localhost"))
        self.port_var = tk.StringVar(value=str(settings.get("connect_port", 4443)))
        self.seat_var = tk.StringVar(value=settings.get("connect_seat", "South"))
        self.table_var = tk.StringVar(value=settings.get("table_id", "local1"))
        self.name_var = tk.StringVar(value=settings.get("connect_name", "Player"))

        frame = ttk.Frame(self, padding=10)
        frame.pack(fill="both", expand=True)
        pad = {'padx': 6, 'pady': 4}

        ttk.Label(frame, text="Host:").grid(row=0, column=0, sticky="e", **pad)
        ttk.Entry(frame, textvariable=self.host_var, width=20).grid(row=0, column=1, **pad)
        ttk.Label(frame, text="Port:").grid(row=1, column=0, sticky="e", **pad)
        ttk.Entry(frame, textvariable=self.port_var, width=8).grid(row=1, column=1, sticky="w", **pad)
        ttk.Label(frame, text="Seat:").grid(row=2, column=0, sticky="e", **pad)
        ttk.Combobox(frame, textvariable=self.seat_var, values=SEAT_ORDER, state="readonly", width=10).grid(
            row=2, column=1, sticky="w", **pad)
        ttk.Label(frame, text="Table:").grid(row=3, column=0, sticky="e", **pad)
        ttk.Entry(frame, textvariable=self.table_var, width=20).grid(row=3, column=1, **pad)
        ttk.Label(frame, text="Name:").grid(row=4, column=0, sticky="e", **pad)
        ttk.Entry(frame, textvariable=self.name_var, width=20).grid(row=4, column=1, **pad)

        btns = ttk.Frame(frame)
        btns.grid(row=5, column=0, columnspan=2, pady=(10, 0), sticky="ew")
        ttk.Button(btns, text="Connect", command=self.on_connect).pack(side="right")
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right", padx=6)

    def on_connect(self):
        host = self.host_var.get().strip() or "localhost"
        port = self.port_var.get().strip()
        seat = self.seat_var.get()
        table = self.table_var.get().strip() or "local1"
        name = self.name_var.get().strip() or "Player"

        try:
            int(port)
        except ValueError:
            messagebox.showerror("Invalid port", "Port must be an integer.")
            return

        letter = SEAT_LETTER[seat]
        self.app.settings.update({
            "connect_host": host,
            "connect_port": int(port),
            "connect_seat": seat,
            "table_id": table,
            "connect_name": name,
        })
        save_settings(self.app.settings)

        # Browser front-end URL (proxies websockets to the BEN server).
        url = (
            f"http://{host}:8080/app/bridge.html?"
            f"{letter}=x&table={table}&seat={letter}&name={name}&server={host}:{port}"
        )
        try:
            webbrowser.open(url)
        except Exception as ex:
            messagebox.showerror("Error", f"Could not open browser: {ex}")
            return
        self.destroy()


class BridgeApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("BEN Bridge")
        self.geometry("760x520")
        self.configure(bg="#1f3a5f")

        self.settings = load_settings()
        self.server = ServerProcess(self._log_root)

        self._build_menubar()
        self._build_status_area()

        self.protocol("WM_DELETE_WINDOW", self.on_exit)
        signal.signal(signal.SIGINT, lambda *_: self.on_exit())
        signal.signal(signal.SIGTERM, lambda *_: self.on_exit())

        # Keep a handle to the Local-server dialog so log output can go there.
        self._server_dialog = None

    def _build_menubar(self):
        mb = tk.Menu(self)

        file_menu = tk.Menu(mb, tearoff=0)
        file_menu.add_command(label="Exit", command=self.on_exit)
        mb.add_cascade(label="File", menu=file_menu)

        server_menu = tk.Menu(mb, tearoff=0)
        server_menu.add_command(label="Start local bridge server...", command=self.show_local_server)
        server_menu.add_command(label="Connect to local bridge server...", command=self.show_connect)
        mb.add_cascade(label="Server", menu=server_menu)

        help_menu = tk.Menu(mb, tearoff=0)
        help_menu.add_command(label="About", command=self.show_about)
        mb.add_cascade(label="Help", menu=help_menu)

        self.configure(menu=mb)

    def _build_status_area(self):
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)

        header = ttk.Label(
            outer,
            text="BEN Bridge — choose 'Server ▸ Start local bridge server…' to host,\n"
                 "or 'Server ▸ Connect to local bridge server…' to join.",
            anchor="center", justify="center")
        header.pack(pady=(0, 8))

        self.root_log = tk.Text(outer, height=18, bg="#101820", fg="white", state="disabled", wrap="word")
        self.root_log.pack(fill="both", expand=True)
        self.root_log.tag_configure("red", foreground="#FF7F50")
        self.root_log.tag_configure("green", foreground="#90EE90")
        self.root_log.tag_configure("yellow", foreground="#FFD700")

    def _log_root(self, text, color=None):
        def _inner():
            self.root_log.configure(state="normal")
            if color:
                self.root_log.insert("end", text, color)
            else:
                self.root_log.insert("end", text)
            self.root_log.configure(state="disabled")
            self.root_log.see("end")
            # Also mirror into the local-server dialog if open
            if self._server_dialog is not None:
                try:
                    self._server_dialog.log(text, color)
                except Exception:
                    pass
        try:
            self.after(0, _inner)
        except Exception:
            pass

    def show_local_server(self):
        if self._server_dialog is not None and self._server_dialog.winfo_exists():
            self._server_dialog.lift()
            return
        dlg = LocalServerDialog(self, self)
        self._server_dialog = dlg
        def _cleanup():
            self._server_dialog = None
        dlg.bind("<Destroy>", lambda _e: _cleanup())

    def show_connect(self):
        ConnectDialog(self, self)

    def show_about(self):
        messagebox.showinfo(
            "About BEN Bridge",
            "BEN Bridge — Q-Plus style front-end.\n\n"
            "Use 'Server ▸ Start local bridge server…' to host a table on this\n"
            "machine. Other humans connect with 'Server ▸ Connect to local\n"
            "bridge server…' from their own machine/browser.\n\n"
            "Up to 4 human seats per table; empty seats play as BEN bots."
        )

    def on_exit(self):
        try:
            if self.server.is_running():
                self.server.stop()
        finally:
            self.destroy()


if __name__ == "__main__":
    app = BridgeApp()
    app.mainloop()
