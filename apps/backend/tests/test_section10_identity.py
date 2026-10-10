"""Signed-session PostgreSQL identity tests; configured test provider is not production SSO."""
import json
import time
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import jwt
import pytest
import test_m6_http_integration as m6
import test_section10_crypto as crypto
from fastapi.testclient import TestClient

from ago.identity_factors import totp
from ago.identity_security_store import IdentitySecurityStore
from ago.repository_ports import IdentitySecurityStorePort
from ago.security import AuthenticationError, Principal, SessionTokens
from ago.security_controls import SecurityControls

case = m6.case
factor_environment = crypto.factor_environment
oidc_keys = crypto.oidc_keys
post = m6.post
URL = '/v1/security'


def enroll(client, headers, password):
    pending = post(client, URL+'/mfa/enroll', headers, {'password': password})
    enabled = post(client, URL+'/mfa/confirm', {}, {'enrollment_token': pending['enrollment_token'],
                    'code': totp(pending['secret_once'], int(time.time())//30)})
    return pending, enabled['recovery_codes_once']


def login(client, info, email, password, code=None, expected=200):
    body = {'tenant_id': info['tenant'], 'email': email, 'password': password}
    if code:
        body['factor_code'] = code
    result = post(client, '/v1/sessions', {}, body, expected=expected)
    return {'Authorization': 'Bearer '+result['access_token']} if expected == 200 else result


def test_mfa_encryption_login_recovery_replay_and_old_session_revocation(case, factor_environment):
    client, headers, info = case
    pending, codes = enroll(client, headers['founder'], 'founder-test-password-123')
    factor = info['db'].execute('SELECT ciphertext FROM ago_mfa_factors WHERE user_id=%s', (info['founder'],)).fetchone()
    assert pending['secret_once'] not in factor['ciphertext']
    assert client.get('/v1/console/me', headers=headers['founder']).status_code == 401
    login(client, info, 'm6founder@example.test', 'founder-test-password-123', expected=401)
    current = login(client, info, 'm6founder@example.test', 'founder-test-password-123', codes[0])
    assert client.get('/v1/console/me', headers=current).status_code == 200
    login(client, info, 'm6founder@example.test', 'founder-test-password-123', codes[0], expected=401)
    step = int(time.time())//30+1
    current = login(client, info, 'm6founder@example.test', 'founder-test-password-123', totp(pending['secret_once'], step))
    login(client, info, 'm6founder@example.test', 'founder-test-password-123', totp(pending['secret_once'], step), expected=401)
    post(client, URL+'/mfa/enroll', current, {'password': 'founder-test-password-123'}, expected=403)
    post(client, URL+'/mfa/confirm', {}, {'enrollment_token': pending['enrollment_token'], 'code': '000000'}, expected=401)
    audit = info['db'].execute("SELECT metadata FROM ago_security_audit WHERE tenant_id=%s AND action LIKE 'mfa.%%'", (info['tenant'],)).fetchall()
    assert pending['secret_once'] not in str(audit) and codes[0] not in str(audit)


def test_secure_invitation_fixed_role_expiry_and_single_use(case, factor_environment, monkeypatch):
    client, headers, info = case
    body = {'kind': 'invitation', 'email': 'new-member@example.test', 'department_id': info['research']}
    post(client, URL+'/tickets', headers['reviewer1'], body, expected=403)
    post(client, URL+'/tickets', headers['founder'], body | {'roles': ['founder']}, expected=422)
    post(client, URL+'/tickets', headers['founder'], body | {'department_id': str(uuid4())}, expected=403)
    ticket = post(client, URL+'/tickets', headers['founder'], body)
    stored = info['db'].execute('SELECT token_hash FROM ago_identity_tickets WHERE id=%s', (ticket['id'],)).fetchone()
    assert ticket['token_once'] != stored['token_hash']
    redemption = {'token': ticket['token_once'], 'email': body['email'], 'password': 'new-member-password-123'}
    post(client, URL+'/tickets/redeem', {}, redemption | {'email': 'attacker@example.test'}, expected=401)
    pending = post(client, URL+'/tickets/redeem', {}, redemption)
    post(client, URL+'/tickets/redeem', {}, redemption, expected=401)
    enabled = post(client, URL+'/mfa/confirm', {}, {'enrollment_token': pending['enrollment_token'],
        'code': totp(pending['secret_once'], int(time.time())//30)})
    monkeypatch.setenv('AGO_IDENTITY_POLICY', 'mfa')
    login(client, info, body['email'], redemption['password'], expected=401)
    member = login(client, info, body['email'], redemption['password'], enabled['recovery_codes_once'][0])
    profile = client.get('/v1/console/me', headers=member).json()
    assert profile['roles'] == ['member'] and 'approval:decide' not in profile['permissions']
    post(client, URL+'/tickets', member, body, expected=403)
    expired = post(client, URL+'/tickets', headers['founder'], body | {'email': 'expired@example.test'})
    info['db'].execute("UPDATE ago_identity_tickets SET expires_at=now()-interval '1 second' WHERE id=%s", (expired['id'],))
    post(client, URL+'/tickets/redeem', {}, redemption | {'token': expired['token_once'], 'email': 'expired@example.test'}, expected=401)


def test_independent_recovery_preserves_mfa_roles_and_revokes_sessions(case, factor_environment):
    client, headers, info = case
    _, codes = enroll(client, headers['reviewer1'], 'reviewer-test-password-123')
    current = login(client, info, 'm6reviewer1@example.test', 'reviewer-test-password-123', codes[0])
    post(client, URL+'/tickets', headers['founder'], {'kind': 'recovery', 'email': 'm6founder@example.test', 'department_id': info['executive']}, expected=403)
    ticket = post(client, URL+'/tickets', headers['founder'], {'kind': 'recovery', 'email': 'm6reviewer1@example.test', 'department_id': info['research']})
    body = {'token': ticket['token_once'], 'email': 'm6reviewer1@example.test', 'password': 'corrected-reviewer-password-123'}
    post(client, URL+'/tickets/redeem', {}, body, expected=401)
    assert info['db'].execute('SELECT used_at FROM ago_identity_tickets WHERE id=%s', (ticket['id'],)).fetchone()['used_at'] is None
    post(client, URL+'/tickets/redeem', {}, body | {'factor_code': codes[1]})
    assert client.get('/v1/console/me', headers=current).status_code == 401
    renewed = login(client, info, body['email'], body['password'], codes[2])
    assert client.get('/v1/console/me', headers=renewed).json()['roles'] == ['reviewer']
    assert info['db'].execute('SELECT 1 FROM ago_mfa_factors WHERE user_id=%s', (info['reviewer1'],)).fetchone()
    post(client, URL+'/tickets/redeem', {}, body | {'factor_code': codes[3]}, expected=401)


def test_revoked_issuer_cannot_redeem_outstanding_invitation(case, factor_environment):
    client, headers, info = case
    ticket = post(client, URL+'/tickets', headers['founder'], {'kind': 'invitation', 'email': 'revoked@example.test', 'department_id': info['research']})
    SecurityControls(info['db']).revoke_grant(info['tenant'], 'founder', 'security:manage')
    post(client, URL+'/tickets/redeem', {}, {'token': ticket['token_once'], 'email': 'revoked@example.test', 'password': 'strong-new-user-password-123'}, expected=401)


def test_sso_browser_state_pkce_mapping_local_roles_and_handoff_replay(case, factor_environment, oidc_keys, monkeypatch):
    client, headers, info = case
    provider, key, claims = oidc_keys
    def exchange(code, verifier, nonce):
        assert code == 'test-authorization-code' and 43 <= len(verifier) <= 128
        signed = jwt.encode(claims | {'nonce': nonce, 'roles': ['founder']}, key, algorithm='RS256', headers={'kid': 'reviewed-key'})
        return provider.verify(signed, nonce)
    monkeypatch.setattr(provider, 'exchange', exchange)
    client.app.state.repository_overrides = {IdentitySecurityStorePort: lambda db, repositories:
        IdentitySecurityStore(db, repositories=repositories, provider=provider)}
    post(client, URL+'/sso/bindings', headers['founder'], {'user_id': info['reviewer1'], 'subject': claims['sub']})
    post(client, URL+'/sso/bindings', headers['reviewer1'], {'user_id': info['reviewer2'], 'subject': 'attacker'}, expected=403)
    with TestClient(client.app, base_url='https://testserver', follow_redirects=False) as browser:
        started = post(browser, URL+'/sso/start', {}, {'tenant_id': info['tenant']})
        query = parse_qs(urlsplit(started['authorization_url']).query)
        assert query['code_challenge_method'] == ['S256'] and len(query['code_challenge'][0]) == 43
        assert browser.cookies.get('ago_sso_browser')
        state = query['state'][0]
        with TestClient(client.app, base_url='https://testserver', follow_redirects=False) as attacker:
            assert attacker.get(URL+'/sso/callback', params={'state': state, 'code': 'test-authorization-code'}).status_code == 401
        callback = browser.get(URL+'/sso/callback', params={'state': state, 'code': 'test-authorization-code'})
        assert callback.status_code == 303 and callback.headers['location'] == '/workspace/'
        assert 'HttpOnly' in callback.headers['set-cookie'] and 'Secure' in callback.headers['set-cookie']
        assert browser.get(URL+'/sso/callback', params={'state': state, 'code': 'test-authorization-code'}).status_code == 401
        handoff = browser.get(URL+'/sso/session')
        assert handoff.status_code == 200 and 'no-store' in handoff.headers['cache-control']
        actor = SessionTokens('m6-integration-test-signing-key-123456789').verify(handoff.json()['access_token'])
        assert actor.subject == info['reviewer1'] and actor.roles == ('reviewer',)
        assert browser.get(URL+'/sso/session').status_code == 401
        monkeypatch.setenv('AGO_IDENTITY_POLICY', 'oidc')
        login(client, info, 'm6reviewer1@example.test', 'reviewer-test-password-123', expected=401)


def test_mfa_reencryption_is_bounded_and_idempotent(case, factor_environment, monkeypatch):
    client, headers, info = case
    _, codes = enroll(client, headers['founder'], 'founder-test-password-123')
    current = login(client, info, 'm6founder@example.test', 'founder-test-password-123', codes[0])
    factor_environment['current'] = 'second'
    factor_environment['keys']['second'] = crypto.base64.urlsafe_b64encode(crypto.secrets.token_bytes(32)).decode()
    monkeypatch.setenv('AGO_MFA_KEYS', json.dumps(factor_environment))
    assert post(client, URL+'/mfa/rotate', current)['reencrypted'] == 1
    assert post(client, URL+'/mfa/rotate', current)['reencrypted'] == 0
    factor_environment['keys'].pop('first')
    monkeypatch.setenv('AGO_MFA_KEYS', json.dumps(factor_environment))
    login(client, info, 'm6founder@example.test', 'founder-test-password-123', codes[1])
    with pytest.raises(PermissionError):
        IdentitySecurityStore(info['db']).rotate_factors(actor=Principal(info['founder'], str(uuid4()), ('founder',)))


def test_production_startup_never_falls_back_when_vault_missing(monkeypatch):
    from ago.main import create_app
    monkeypatch.setenv('AGO_ENVIRONMENT', 'production')
    monkeypatch.delenv('AGO_VAULT_URL', raising=False)
    with pytest.raises(AuthenticationError, match='provider unavailable'):
        create_app()
