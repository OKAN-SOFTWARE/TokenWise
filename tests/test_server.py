import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from tokenwise.server import TokenWiseServer


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.server = TokenWiseServer(("127.0.0.1", 0), Path(self.folder.name) / "runs.sqlite3")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()
        self.folder.cleanup()

    def request(self, url, payload=None):
        body = json.dumps(payload).encode() if payload is not None else None
        headers = {"Content-Type": "application/json"} if body is not None else {}
        with urlopen(Request(self.base + url, data=body, headers=headers), timeout=2) as response:
            return response.status, json.loads(response.read())

    def test_health_does_not_enable_aws(self):
        status, result = self.request("/api/health")
        self.assertEqual(status, 200)
        self.assertFalse(result["aws_calls"])

    def test_simulation_and_ledger(self):
        status, sim = self.request("/api/simulate", {"requests_per_day": 20})
        self.assertEqual(status, 200)
        self.assertEqual(sim["result"]["requests"], 600)
        _, runs = self.request("/api/runs")
        self.assertEqual(len(runs["runs"]), 1)
        self.assertNotIn("prompt", runs["runs"][0])

    def test_prompt_inspection(self):
        status, analysis = self.request("/api/inspect", {"prompt": "repeat\nrepeat"})
        self.assertEqual(status, 200)
        self.assertEqual(analysis["duplicate_lines"], 1)

    def test_rejects_invalid_scenarios(self):
        with self.assertRaises(HTTPError) as context:
            self.request("/api/simulate", {"requests_per_day": -1})
        self.assertEqual(context.exception.code, 400)

    def test_static_dashboard_served(self):
        with urlopen(self.base + "/", timeout=2) as response:
            html = response.read().decode()
        self.assertIn("TokenWise", html)
        self.assertIn("/static/app.js", html)


if __name__ == "__main__":
    unittest.main()
