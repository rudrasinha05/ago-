"""Real RSA/AEAD/TOTP and TLS transport evidence, not production attestation."""
import base64
import json
import secrets
import ssl
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs
from uuid import uuid4

import jwt
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from ago.identity_factors import decrypt_factor, encrypt_factor, factor_step, totp
from ago.security import AuthenticationError, Principal
from ago.security_material import RotatingSessionTokens, private_file, vault_material
from ago.sso_provider import OIDCProvider


@pytest.fixture
def factor_environment(monkeypatch):
    value = {'current': 'first', 'keys': {'first': base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()}}
    monkeypatch.setenv('AGO_MFA_KEYS', json.dumps(value))
    return value


def test_aead_tenant_user_binding_and_real_key_rotation(factor_environment, monkeypatch):
    tenant, user = str(uuid4()), str(uuid4())
    encrypted = encrypt_factor('private-factor-value', tenant, user)
    assert 'private-factor-value' not in encrypted
    assert decrypt_factor(encrypted, tenant, user) == 'private-factor-value'
    for t, u in ((str(uuid4()), user), (tenant, str(uuid4()))):
        with pytest.raises(AuthenticationError):
            decrypt_factor(encrypted, t, u)
    factor_environment['current'] = 'second'
    factor_environment['keys']['second'] = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    monkeypatch.setenv('AGO_MFA_KEYS', json.dumps(factor_environment))
    assert decrypt_factor(encrypted, tenant, user) == 'private-factor-value'
    rotated = encrypt_factor(decrypt_factor(encrypted, tenant, user), tenant, user)
    del factor_environment['keys']['first']
    monkeypatch.setenv('AGO_MFA_KEYS', json.dumps(factor_environment))
    assert decrypt_factor(rotated, tenant, user) == 'private-factor-value'
    with pytest.raises(AuthenticationError):
        decrypt_factor(encrypted, tenant, user)


@pytest.mark.parametrize('seconds,expected', [(59, '287082'), (1111111109, '081804'), (1111111111, '050471'), (1234567890, '005924')])
def test_rfc6238_truncated_six_digit_vectors_and_replay(seconds, expected):
    secret = base64.b32encode(b'12345678901234567890').decode()
    assert totp(secret, seconds//30) == expected
    assert factor_step(secret, expected, now=seconds) == seconds//30
    with pytest.raises(AuthenticationError):
        factor_step(secret, expected, last_step=seconds//30, now=seconds)


def test_signing_rotation_overlap_deadline_removed_key_and_epoch():
    now = int(time.time())
    first, second = secrets.token_urlsafe(48), secrets.token_urlsafe(48)
    actor = Principal(str(uuid4()), str(uuid4()), ('member',), 3)
    old = RotatingSessionTokens(json.dumps({'current': 'first', 'keys': {'first': {'secret': first}}}), now=now)
    token = old.issue(actor, now=now)
    keys = {'current': 'second', 'keys': {'second': {'secret': second}, 'first': {'secret': first, 'verify_until': now+60}}}
    current = RotatingSessionTokens(json.dumps(keys), now=now)
    assert current.verify(token, now=now+59) == actor
    assert current.issue(actor, now=now).startswith('second.')
    with pytest.raises(AuthenticationError):
        current.verify(token, now=now+60)
    keys['keys']['first']['verify_until'] = now+901
    with pytest.raises(AuthenticationError):
        RotatingSessionTokens(json.dumps(keys), now=now)


@pytest.fixture
def oidc_keys(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    jwk.update(kid='reviewed-key', alg='RS256', use='sig')
    path = tmp_path/'jwks.json'
    path.write_text(json.dumps({'keys': [jwk]}))
    config = {'issuer': 'https://identity.example.test', 'client_id': 'ago-reviewed-client',
        'authorization_endpoint': 'https://identity.example.test/authorize',
        'token_endpoint': 'https://identity.example.test/token',
        'redirect_uri': 'https://ago.example.test/v1/security/sso/callback', 'jwks_file': str(path)}
    now = int(time.time())
    claims = {'iss': config['issuer'], 'sub': 'explicit-bound-subject', 'aud': config['client_id'],
              'iat': now, 'exp': now+300, 'auth_time': now, 'nonce': 'browser-nonce', 'amr': ['mfa']}
    return OIDCProvider(config), key, claims


def test_actual_signed_oidc_claims_and_provider_role_is_not_local_authority(oidc_keys):
    provider, key, claims = oidc_keys
    token = jwt.encode(claims | {'roles': ['founder']}, key, algorithm='RS256', headers={'kid': 'reviewed-key'})
    assert provider.verify(token, 'browser-nonce')['sub'] == 'explicit-bound-subject'


@pytest.mark.parametrize('change', [{'iss': 'https://attacker.test'}, {'aud': 'other-client'}, {'nonce': 'stolen'},
                                  {'amr': ['pwd']}, {'auth_time': 1}, {'exp': 1}, {'azp': 'other-client'}])
def test_signed_oidc_wrong_context_cannot_authenticate(oidc_keys, change):
    provider, key, claims = oidc_keys
    token = jwt.encode(claims | change, key, algorithm='RS256', headers={'kid': 'reviewed-key'})
    with pytest.raises(AuthenticationError):
        provider.verify(token, 'browser-nonce')


def test_oidc_rejects_none_algorithm_and_provider_redirect_substitution(oidc_keys):
    provider, _, claims = oidc_keys
    with pytest.raises(AuthenticationError):
        provider.verify(jwt.encode(claims, key='', algorithm='none', headers={'kid': 'reviewed-key'}), 'browser-nonce')
    with pytest.raises(AuthenticationError):
        OIDCProvider(provider.config | {'token_endpoint': 'https://attacker.test/token'})


def test_real_verified_tls_vault_and_no_redirect_or_permissive_secret_file(tmp_path, monkeypatch, factor_environment, oidc_keys):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'localhost')])
    now = datetime.now(timezone.utc)
    certificate = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1))
        .not_valid_after(now+timedelta(days=1)).add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost')]), False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), True).sign(key, hashes.SHA256()))
    ca, pem = tmp_path/'ca.pem', tmp_path/'key.pem'
    ca.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    pem.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    token = tmp_path/'vault.token'
    token.write_text('private-local-fixture-token')
    token.chmod(0o600)
    secret = secrets.token_urlsafe(48)
    material = {'AGO_SESSION_SECRET': secret, 'AGO_SESSION_KEYRING': json.dumps({'current': 'first', 'keys': {'first': {'secret': secret}}}),
                'AGO_POSTGRES_DSN': 'postgresql://fixture-only', 'AGO_MFA_KEYS': json.dumps(factor_environment)}
    configured, signing_key, claims = oidc_keys
    class Handler(BaseHTTPRequestHandler):
        status = 200
        def do_GET(self):
            assert self.headers['X-Vault-Token'] == 'private-local-fixture-token'
            self.send_response(self.status)
            self.send_header('Location', 'https://attacker.test/stolen')
            self.end_headers()
            self.wfile.write(json.dumps({'data': {'data': material, 'metadata': {'version': 1, 'destroyed': False, 'deletion_time': ''}}}).encode())
        def log_message(self, *_):
            pass
        def do_POST(self):
            values = parse_qs(self.rfile.read(int(self.headers['Content-Length'])).decode())
            assert values['code_verifier'] == ['v'*43]
            assert values['client_id'] == [configured.config['client_id']]
            self.send_response(self.status)
            self.end_headers()
            signed = jwt.encode(claims | {'iss': configured.config['issuer']}, signing_key,
                                algorithm='RS256', headers={'kid': 'reviewed-key'})
            self.wfile.write(json.dumps({'id_token': signed}).encode())
    server = HTTPServer(('127.0.0.1', 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(ca, pem)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv('AGO_VAULT_URL', f'https://localhost:{server.server_port}')
    monkeypatch.setenv('AGO_VAULT_KV_PATH', 'secret/data/ago')
    monkeypatch.setenv('AGO_VAULT_CA_FILE', str(ca))
    monkeypatch.setenv('AGO_VAULT_TOKEN_FILE', str(token))
    address = f'https://localhost:{server.server_port}'
    configured = OIDCProvider(configured.config | {'issuer': address, 'authorization_endpoint': address+'/authorize',
                                  'token_endpoint': address+'/token', 'ca_file': str(ca)})
    try:
        assert vault_material() == material
        assert configured.exchange('local-test-provider-code', 'v'*43, 'browser-nonce')['sub'] == claims['sub']
        with pytest.raises(AuthenticationError):
            configured.exchange('local-test-provider-code', 'v'*43, 'wrong-browser')
        monkeypatch.setenv('AGO_VAULT_URL', f'https://127.0.0.1:{server.server_port}')
        with pytest.raises(AuthenticationError, match='provider unavailable'):
            vault_material()
        monkeypatch.setenv('AGO_VAULT_URL', f'https://localhost:{server.server_port}')
        Handler.status = 302
        with pytest.raises(AuthenticationError, match='provider unavailable'):
            vault_material()
        token.chmod(0o644)
        with pytest.raises(ValueError):
            private_file(str(token))
        link = tmp_path/'symlink'
        link.symlink_to(token)
        with pytest.raises(OSError):
            private_file(str(link))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
