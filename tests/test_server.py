import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from app.server import PlanHandler


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), PlanHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_plan_endpoint_is_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            source = repository / "AccountService.java"
            source.write_text("class AccountService {}")
            connection = HTTPConnection("127.0.0.1", self.server.server_port)
            body = json.dumps(
                {"repository": str(repository), "request": "Plan account changes"}
            )
            with patch(
                "app.server.create_plan",
                return_value={
                    "mode": "plan-only",
                    "humanApprovalRequired": True,
                },
            ):
                connection.request(
                    "POST", "/plans", body, {"Content-Type": "application/json"}
                )
                response = connection.getresponse()
                payload = json.loads(response.read())

            self.assertEqual(200, response.status)
            self.assertEqual("plan-only", payload["mode"])
            self.assertTrue(payload["humanApprovalRequired"])
            self.assertEqual("class AccountService {}", source.read_text())

    def test_unknown_endpoint_returns_not_found(self):
        connection = HTTPConnection("127.0.0.1", self.server.server_port)
        connection.request("GET", "/unknown")
        self.assertEqual(404, connection.getresponse().status)

    def test_plan_endpoint_rejects_empty_request(self):
        connection = HTTPConnection("127.0.0.1", self.server.server_port)
        connection.request(
            "POST",
            "/plans",
            json.dumps({"repository": "/tmp", "request": " "}),
            {"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        self.assertEqual(400, response.status)


if __name__ == "__main__":
    unittest.main()
