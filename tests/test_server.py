import json
import os
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
            plans = repository / "plans"
            source = repository / "AccountService.java"
            source.write_text("class AccountService {}")
            connection = HTTPConnection("127.0.0.1", self.server.server_port)
            body = json.dumps(
                {"repository": str(repository), "request": "Plan account changes"}
            )
            with patch.dict(os.environ, {"PLANS_DIR": str(plans)}), patch(
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
            self.assertRegex(payload["runId"], r"^[0-9a-f-]{36}$")
            self.assertTrue(payload["createdAt"].endswith("+00:00"))
            self.assertTrue((plans / f"{payload['runId']}.json").exists())
            self.assertEqual("class AccountService {}", source.read_text())

    def test_unknown_endpoint_returns_not_found(self):
        connection = HTTPConnection("127.0.0.1", self.server.server_port)
        connection.request("GET", "/unknown")
        self.assertEqual(404, connection.getresponse().status)

    def test_saved_plans_can_be_listed_and_read(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"PLANS_DIR": directory}
        ):
            saved = Path(directory) / "abc.json"
            saved.write_text(
                json.dumps(
                    {
                        "runId": "abc",
                        "createdAt": "2026-01-01T00:00:00+00:00",
                        "request": "test",
                        "mode": "plan-only",
                    }
                )
            )
            connection = HTTPConnection("127.0.0.1", self.server.server_port)
            connection.request("GET", "/plans")
            response = connection.getresponse()
            self.assertEqual(200, response.status)
            self.assertEqual("abc", json.loads(response.read())["plans"][0]["runId"])

            connection.request("GET", "/plans/abc")
            response = connection.getresponse()
            self.assertEqual(200, response.status)
            self.assertEqual("abc", json.loads(response.read())["runId"])

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

    def test_plan_endpoint_rejects_repository_outside_configured_root(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            connection = HTTPConnection("127.0.0.1", self.server.server_port)
            with patch.dict(os.environ, {"PROJECT_ROOTS": root}):
                connection.request(
                    "POST",
                    "/plans",
                    json.dumps({"repository": outside, "request": "read files"}),
                    {"Content-Type": "application/json"},
                )
                response = connection.getresponse()
            self.assertEqual(400, response.status)

    def test_plan_endpoint_accepts_repository_under_any_configured_root(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            repository = Path(second) / "project"
            repository.mkdir()
            connection = HTTPConnection("127.0.0.1", self.server.server_port)
            with patch.dict(os.environ, {"PROJECT_ROOTS": os.pathsep.join([first, second])}), patch(
                "app.server.create_plan",
                return_value={
                    "mode": "plan-only",
                    "humanApprovalRequired": True,
                },
            ):
                connection.request(
                    "POST",
                    "/plans",
                    json.dumps({"repository": str(repository), "request": "read files"}),
                    {"Content-Type": "application/json"},
                )
                response = connection.getresponse()
            self.assertEqual(200, response.status)


if __name__ == "__main__":
    unittest.main()
