import importlib.util
import json
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from http.server import ThreadingHTTPServer

spec = importlib.util.spec_from_file_location("metrics", Path(__file__).with_name("pc-metrics.py"))
metrics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metrics)


class MetricsTests(unittest.TestCase):
    def test_private_bind_only(self):
        for address in ("127.0.0.1", "192.168.88.20", "10.1.2.3", "172.31.2.3"):
            self.assertTrue(metrics.private_address(address))
        for address in ("0.0.0.0", "8.8.8.8", "172.32.0.1", "::", "localhost"):
            self.assertFalse(metrics.private_address(address))

    def test_real_windows_metrics_and_read_only_routes(self):
        sampler = metrics.Sampler()
        sampler.sample()
        time.sleep(0.1)
        sampler.sample()
        self.assertIsNotNone(sampler.data)
        server = ThreadingHTTPServer(("127.0.0.1", 0), metrics.make_handler(sampler))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}"
        try:
            with urllib.request.urlopen(url + "/metrics.json") as response:
                body = json.load(response)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
            self.assertEqual(set(body), {"schema", "updated", "cpu_percent", "memory_percent", "disk_percent"})
            for key in ("cpu_percent", "memory_percent", "disk_percent"):
                self.assertGreaterEqual(body[key], 0)
                self.assertLessEqual(body[key], 100)
            for path in ("/", "/../worker.key", "/metrics.json?extra=1"):
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(url + path)
                self.assertEqual(error.exception.code, 404)
                error.exception.close()
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(urllib.request.Request(url + "/metrics.json", data=b"{}"))
            self.assertEqual(error.exception.code, 501)
            error.exception.close()
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
