"""Frontend source integrity and real packaged HTTP/CSP perimeter contracts."""
import base64
import hashlib
import importlib.util
import re
from pathlib import Path

from fastapi.testclient import TestClient

from ago import api_m2
from ago.main import create_app

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('frontend_guard', ROOT/'scripts/check_frontend_architecture.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def test_frontend_source_contract_has_no_drift():
    assert guard.check() == []


def test_packaged_next_routes_and_inline_scripts_have_exact_csp_hashes():
    # Builds are mandatory in primary CI; local targeted tests package the export first.
    app = create_app()
    with TestClient(app) as client:
        for route in ['', 'strategy/', 'governance/', 'organization/', 'knowledge/',
                      'tools/', 'calendar/', 'twin/']:
            response = client.get('/workspace/'+route)
            assert response.status_code == 200
            assert 'Organization ID' in response.text
            csp = response.headers['content-security-policy']
            assert "script-src 'self'" in csp and "connect-src 'self'" in csp
            assert "'unsafe-inline'" not in csp.split('script-src')[1].split(';')[0]
            assert "frame-ancestors 'none'" in csp
            for attrs, text in re.findall(r'<script\b([^>]*)>(.*?)</script>', response.text, re.DOTALL):
                if 'src=' not in attrs and text:
                    value = base64.b64encode(hashlib.sha256(text.encode()).digest()).decode()
                    assert "'sha256-"+value+"'" in csp
            assert 'no-store' in response.headers['cache-control']
            assert response.headers['x-frame-options'] == 'DENY'
            assert 'access-control-allow-origin' not in response.headers


def test_public_next_export_never_opens_private_api_or_filesystem():
    app = create_app()
    app.dependency_overrides[api_m2.db_connection] = lambda: object()
    with TestClient(app) as client:
        assert client.get('/workspace/').status_code == 200
        for path in ['/v1/console/me', '/v1/tasks', '/v1/brain/goals']:
            assert client.get(path).status_code == 401
        assert client.get('/workspace/unknown/').status_code == 404
        assert client.get('/workspace/%2e%2e/architecture_policy.json').status_code == 404
