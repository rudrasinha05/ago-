"""Local deployment perimeter, failure alerts and isolated recovery controls."""
import json
import os
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from ago import local_ops


def test_actual_loopback_health_and_failure_alert(monkeypatch):
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    class Handler(BaseHTTPRequestHandler):
        ready = True

        def do_GET(self):
            ready = self.path == "/health/live" or self.ready
            self.send_response(200 if ready else 503)
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok" if self.path.endswith("live")
                                        else "ready" if ready else "not_ready"}).encode())

        def log_message(self, *_args):
            pass

    with HTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            assert not local_ops.monitor_local(port=server.server_port)["alert"]
            Handler.ready = False
            result = local_ops.monitor_local(port=server.server_port)
            assert result["live"]["healthy"]
            assert not result["ready"]["healthy"] and result["alert"]
            assert local_ops.main(["monitor", "--port", str(server.server_port)]) == 2
        finally:
            server.shutdown()
            thread.join(timeout=3)


@pytest.mark.parametrize("payload,status", [
    (b'{"status":"ready"}', 302), (b"invalid private text", 200),
    (b"x" * 65537, 200), (b"[]", 200),
])
def test_monitor_rejects_redirect_malformed_and_unbounded_results(monkeypatch, payload, status):
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    class Client:
        def __init__(self, host, port, timeout):
            assert host == "127.0.0.1" and timeout == 3

        def request(self, method, path):
            assert method == "GET" and path in ("/health/live", "/health/ready")

        def getresponse(self):
            self.status = status
            return self

        def read(self, limit):
            assert limit == 65537
            return payload

        def close(self):
            pass

    assert local_ops.monitor_local(connection=Client)["alert"]


def test_monitor_production_and_invalid_port_refused(monkeypatch):
    monkeypatch.setenv("AGO_ENVIRONMENT", "production")
    with pytest.raises(PermissionError):
        local_ops.monitor_local()
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    with pytest.raises(PermissionError):
        local_ops.monitor_local(port=80)


def test_backup_requires_ready_local_database(monkeypatch, tmp_path):
    monkeypatch.setattr(local_ops, "doctor", lambda: local_ops.LocalDiagnosis(
        True, True, False, False, "ephemeral_on_serve", False))
    with pytest.raises(RuntimeError):
        local_ops.backup_local(tmp_path / "archive.dump", confirmed=True)
    assert not list(tmp_path.iterdir())


def test_restore_refuses_remote_target_and_production(monkeypatch, tmp_path):
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    monkeypatch.setenv("AGO_POSTGRES_DSN", "postgresql://u:p@localhost/ago")
    monkeypatch.setenv("AGO_RESTORE_TEST_DSN", "postgresql://u:p@remote/ago_restore_drill")
    with pytest.raises(PermissionError):
        local_ops.restore_local(tmp_path / "archive.dump", confirmed=True)

    monkeypatch.setenv("AGO_RESTORE_TEST_DSN", "postgresql://u:p@localhost/ago_restore_drill")
    monkeypatch.setenv("AGO_ENVIRONMENT", "production")
    with pytest.raises(PermissionError):
        local_ops.restore_local(tmp_path / "archive.dump", confirmed=True)


def test_actual_ago_start_monitor_stop_alert(monkeypatch):
    dsn = os.getenv("AGO_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("Disposable migrated local PostgreSQL required")
    monkeypatch.setenv("AGO_POSTGRES_DSN", dsn)
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    assert local_ops.doctor().ready
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    process = subprocess.Popen(
        [sys.executable, "-m", "ago.local_ops", "serve", "--port", str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if not local_ops.monitor_local(port=port)["alert"]:
                break
            assert process.poll() is None, "Local AGO failed to start"
            time.sleep(0.1)
        else:
            pytest.fail("Actual AGO readiness timed out")
    finally:
        process.terminate()
        process.wait(timeout=10)
    result = local_ops.monitor_local(port=port)
    assert result["alert"] and not result["live"]["healthy"]
