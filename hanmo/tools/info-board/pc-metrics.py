"""HanMo local PC metrics. No files/process names/credentials are served."""
import argparse
import ctypes
import ipaddress
import json
import os
import shutil
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class MemoryStatus(ctypes.Structure):
    _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
        (name, ctypes.c_ulonglong)
        for name in ("total_phys", "avail_phys", "total_page", "avail_page",
                     "total_virtual", "avail_virtual", "avail_extended")
    ]


def private_address(value):
    try:
        ip = ipaddress.ip_address(value)
        return ip.version == 4 and (ip.is_loopback or any(ip in ipaddress.ip_network(n) for n in
            ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")))
    except ValueError:
        return False


class Sampler:
    def __init__(self):
        self.lock = threading.Lock()
        self.data = None
        self.previous = None

    def sample(self):
        idle, kernel, user = (ctypes.c_ulonglong() for _ in range(3))
        if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
            raise OSError("GetSystemTimes failed")
        values = (idle.value, kernel.value + user.value)
        old = self.previous
        self.previous = values
        if old is None or values[1] <= old[1]:
            return
        cpu = max(0, min(100, 100 * (1 - (values[0] - old[0]) / (values[1] - old[1]))))
        memory = MemoryStatus()
        memory.length = ctypes.sizeof(memory)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
            raise OSError("GlobalMemoryStatusEx failed")
        disk = shutil.disk_usage(os.environ.get("SystemDrive", "C:") + "\\")
        data = {"schema": 1, "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "cpu_percent": round(cpu, 1), "memory_percent": memory.load,
                "disk_percent": round(100 * disk.used / disk.total, 1)}
        with self.lock:
            self.data = data

    def run(self, stop):
        while not stop.is_set():
            try:
                self.sample()
            except OSError:
                with self.lock:
                    self.data = None
            stop.wait(2)


def make_handler(sampler, reader=None):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if not private_address(self.client_address[0]) or (reader and self.client_address[0] != reader):
                self.send_error(403)
                return
            if self.path != "/metrics.json":
                self.send_error(404)
                return
            with sampler.lock:
                data = sampler.data.copy() if sampler.data else None
            if not data:
                self.send_error(503, "Metrics warming up")
                return
            body = json.dumps(data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass
    return Handler


def main():
    parser = argparse.ArgumentParser(description="HanMo PC 使用率（僅本機／私人區域網路）")
    parser.add_argument("--bind", default="127.0.0.1", help="電腦的區域網路 IPv4 位址")
    parser.add_argument("--port", type=int, default=4342)
    parser.add_argument("--reader", help="選填：僅允許這個 X4 Pro IP")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("This collector requires Windows")
    if not private_address(args.bind) or (args.reader and not private_address(args.reader)):
        parser.error("Use a specific private IPv4 address; wildcard/public binding is not supported")
    sampler = Sampler()
    stop = threading.Event()
    threading.Thread(target=sampler.run, args=(stop,), daemon=True).start()
    server = ThreadingHTTPServer((args.bind, args.port), make_handler(sampler, args.reader))
    print(f"資訊看板電腦資料：http://{args.bind}:{args.port}/metrics.json", flush=True)
    print("只提供 CPU、記憶體與系統磁碟使用率；不會上傳 Work Hub。Ctrl+C 停止。", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()


if __name__ == "__main__":
    main()
