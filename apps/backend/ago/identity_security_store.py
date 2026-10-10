"""Owned MFA, single-use employee onboarding/recovery and explicit SSO mappings."""
from __future__ import annotations

import base64
import hashlib
import os
import secrets
from urllib.parse import quote
from uuid import UUID, uuid4

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.identity import IdentityRepository
from ago.identity_factors import decrypt_factor, digest_token, encrypt_factor, factor_step, factor_keys
from ago.login_security import LoginThrottle
from ago.security import AuthenticationError, Principal, hash_password
from ago.security_controls import SecurityControls
from ago.sso_provider import OIDCProvider


class IdentitySecurityStore:
    def __init__(self, db: DatabaseConnection, *, repositories: RepositoryScope | None = None, provider=None):
        self.db = db
        self.repositories = repositories or RepositoryScope(db)
        self.provider = provider

    def _audit(self, actor, action, metadata=None):
        self.repositories.resolve(SecurityControls).audit(action, 'accepted',
            tenant_id=actor.tenant_id, actor_id=actor.subject, metadata=metadata)

    def _human(self, actor):
        controls = self.repositories.resolve(SecurityControls)
        if (not controls.permitted(actor, 'security:manage', actor.tenant_id)
                or not self.db.execute("SELECT 1 FROM ago_employees WHERE tenant_id=%s AND id=%s AND kind='human'",
                                        (actor.tenant_id, actor.subject)).fetchone()):
            raise PermissionError('Authorized human security operator required')

    def _enrollment(self, actor):
        if self.db.execute('SELECT 1 FROM ago_mfa_factors WHERE tenant_id=%s AND user_id=%s',
                            (actor.tenant_id, actor.subject)).fetchone():
            raise PermissionError('Existing MFA cannot be replaced through enrollment')
        secret = base64.b32encode(secrets.token_bytes(20)).decode()
        token = secrets.token_urlsafe(32)
        self.db.execute('DELETE FROM ago_mfa_enrollments WHERE tenant_id=%s AND user_id=%s',
                        (actor.tenant_id, actor.subject))
        self.db.execute('INSERT INTO ago_mfa_enrollments(token_hash,tenant_id,user_id,ciphertext) VALUES(%s,%s,%s,%s)',
            (digest_token(token), actor.tenant_id, actor.subject, encrypt_factor(secret, actor.tenant_id, actor.subject)))
        return {'enrollment_token': token, 'secret_once': secret,
                'otpauth_uri': f'otpauth://totp/AGO:{quote(actor.subject)}?secret={secret}&issuer=AGO&algorithm=SHA1&digits=6&period=30'}

    def begin_factor(self, *, actor: Principal, password: str) -> dict:
        with self.db.transaction():
            user = self.db.execute('SELECT email FROM ago_users WHERE tenant_id=%s AND id=%s AND active=true FOR UPDATE',
                                    (actor.tenant_id, actor.subject)).fetchone()
            if not user:
                raise AuthenticationError('Invalid credentials')
            throttle = self.repositories.resolve(LoginThrottle)
            if not throttle.begin(actor.tenant_id, user['email']):
                raise AuthenticationError('Invalid credentials')
            valid = self.repositories.resolve(IdentityRepository).authenticate(actor.tenant_id, user['email'], password)
            if not valid:
                throttle.failure(actor.tenant_id, user['email'])
            else:
                result = self._enrollment(actor)
                self._audit(actor, 'mfa.enrollment.begin')
        if not valid:
            self.db.commit()
            raise AuthenticationError('Invalid credentials')
        return result

    def confirm_factor(self, *, token: str, code: str) -> dict:
        with self.db.transaction():
            enrollment = self.db.execute('SELECT * FROM ago_mfa_enrollments WHERE token_hash=%s AND expires_at>clock_timestamp() FOR UPDATE',
                                         (digest_token(token),)).fetchone()
            if not enrollment:
                raise AuthenticationError('Invalid credentials')
            actor = Principal(str(enrollment['user_id']), str(enrollment['tenant_id']), ('member',))
            user = self.db.execute('SELECT email FROM ago_users WHERE tenant_id=%s AND id=%s AND active=true FOR UPDATE',
                                    (actor.tenant_id, actor.subject)).fetchone()
            if not user or not self.repositories.resolve(LoginThrottle).begin(actor.tenant_id, user['email']):
                raise AuthenticationError('Invalid credentials')
            try:
                step = factor_step(decrypt_factor(enrollment['ciphertext'], actor.tenant_id, actor.subject), code)
            except AuthenticationError:
                self.repositories.resolve(LoginThrottle).failure(actor.tenant_id, user['email'])
                step = None
            if step is not None:
                self.db.execute('INSERT INTO ago_mfa_factors(tenant_id,user_id,ciphertext,last_step) VALUES(%s,%s,%s,%s)',
                    (actor.tenant_id, actor.subject, enrollment['ciphertext'], step))
                self.db.execute('DELETE FROM ago_mfa_enrollments WHERE token_hash=%s', (digest_token(token),))
                recovery = [secrets.token_urlsafe(24) for _ in range(10)]
                for value in recovery:
                    self.db.execute('INSERT INTO ago_mfa_recovery_codes(tenant_id,user_id,code_hash) VALUES(%s,%s,%s)',
                                    (actor.tenant_id, actor.subject, digest_token(value)))
                self.db.execute('UPDATE ago_users SET session_version=session_version+1 WHERE tenant_id=%s AND id=%s',
                                (actor.tenant_id, actor.subject))
                self._audit(actor, 'mfa.enrollment.confirmed')
        if step is None:
            self.db.commit()
            raise AuthenticationError('Invalid credentials')
        return {'enabled': True, 'recovery_codes_once': recovery}

    def verify_factor(self, *, actor: Principal, code: str | None, required: bool = False) -> None:
        with self.db.transaction():
            factor = self.db.execute('SELECT * FROM ago_mfa_factors WHERE tenant_id=%s AND user_id=%s FOR UPDATE',
                                     (actor.tenant_id, actor.subject)).fetchone()
            if not factor:
                if required or code:
                    raise AuthenticationError('Invalid credentials')
                return
            if not code:
                raise AuthenticationError('Invalid credentials')
            if len(code) == 6:
                step = factor_step(decrypt_factor(factor['ciphertext'], actor.tenant_id, actor.subject), code, factor['last_step'])
                self.db.execute('UPDATE ago_mfa_factors SET last_step=%s WHERE tenant_id=%s AND user_id=%s',
                                (step, actor.tenant_id, actor.subject))
            else:
                used = self.db.execute('DELETE FROM ago_mfa_recovery_codes WHERE tenant_id=%s AND user_id=%s AND code_hash=%s RETURNING code_hash',
                                       (actor.tenant_id, actor.subject, digest_token(code))).fetchone()
                if not used:
                    raise AuthenticationError('Invalid credentials')
            self._audit(actor, 'mfa.factor.accepted')

    def issue_ticket(self, *, actor: Principal, kind: str, email: str, department_id: str) -> dict:
        UUID(department_id)
        email = email.strip().lower()
        if kind not in {'invitation', 'recovery'} or not 3 <= len(email) <= 320 or '@' not in email:
            raise ValueError('Valid identity ticket details required')
        with self.db.transaction():
            self._human(actor)
            if not self.db.execute('SELECT 1 FROM ago_departments WHERE tenant_id=%s AND id=%s',
                                    (actor.tenant_id, department_id)).fetchone():
                raise PermissionError('Same-tenant department required')
            user = self.db.execute('SELECT id,session_version FROM ago_users WHERE tenant_id=%s AND email=%s AND active=true',
                                  (actor.tenant_id, email)).fetchone()
            if kind == 'invitation' and user or kind == 'recovery' and (not user or str(user['id']) == actor.subject):
                raise PermissionError('Invitation must be new; recovery requires a separate human issuer')
            if kind == 'recovery' and not self.db.execute("SELECT 1 FROM ago_employees WHERE tenant_id=%s AND id=%s AND kind='human'",
                                                        (actor.tenant_id, user['id'])).fetchone():
                raise PermissionError('Human employee recovery required')
            identifier, token = str(uuid4()), secrets.token_urlsafe(32)
            hours = 24 if kind == 'invitation' else 0.25
            self.db.execute('''INSERT INTO ago_identity_tickets(id,token_hash,tenant_id,issuer_id,kind,email,department_id,user_id,session_version,expires_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,now()+(%s*interval '1 hour'))''',
                (identifier, digest_token(token), actor.tenant_id, actor.subject, kind, email, department_id,
                 user['id'] if kind == 'recovery' else None, user['session_version'] if kind == 'recovery' else None, hours))
            self._audit(actor, 'identity.ticket.issued', {'ticket_id': identifier, 'kind': kind})
        return {'id': identifier, 'token_once': token, 'kind': kind, 'expires_in_seconds': int(hours*3600)}

    def redeem_ticket(self, *, token: str, email: str, password: str, factor_code: str | None = None) -> dict:
        encoded = hash_password(password)
        factor_denied = False
        with self.db.transaction():
            ticket = self.db.execute('SELECT * FROM ago_identity_tickets WHERE token_hash=%s AND used_at IS NULL AND expires_at>clock_timestamp() FOR UPDATE',
                                    (digest_token(token),)).fetchone()
            if not ticket or ticket['email'] != email.strip().lower():
                raise AuthenticationError('Invalid credentials')
            tenant = str(ticket['tenant_id'])
            issuer = self.db.execute('SELECT active FROM ago_users WHERE tenant_id=%s AND id=%s', (tenant, ticket['issuer_id'])).fetchone()
            if not issuer or not issuer['active']:
                raise AuthenticationError('Invalid credentials')
            try:
                self._human(Principal(str(ticket['issuer_id']), tenant, ()))
            except PermissionError as exc:
                raise AuthenticationError('Invalid credentials') from exc
            if ticket['kind'] == 'invitation':
                user = self.repositories.resolve(IdentityRepository).create_user(tenant, email, password)
                self.repositories.resolve(IdentityRepository).assign_role(tenant, user.user_id, 'member')
                self.db.execute('''INSERT INTO ago_employees(id,tenant_id,department_id,name,kind) VALUES(%s,%s,%s,%s,'human')''',
                                (user.user_id, tenant, ticket['department_id'], 'Invited employee'))
                actor = Principal(user.user_id, tenant, ('member',))
                result = self._enrollment(actor)
            else:
                actor = Principal(str(ticket['user_id']), tenant, ('member',))
                user = self.db.execute('SELECT session_version,active FROM ago_users WHERE tenant_id=%s AND id=%s FOR UPDATE',
                                       (tenant, actor.subject)).fetchone()
                if not user or not user['active'] or user['session_version'] != ticket['session_version']:
                    raise AuthenticationError('Invalid credentials')
                throttle = self.repositories.resolve(LoginThrottle)
                if not throttle.begin(tenant, ticket['email']):
                    raise AuthenticationError('Invalid credentials')
                try:
                    self.verify_factor(actor=actor, code=factor_code, required=os.getenv('AGO_IDENTITY_POLICY') == 'mfa')
                except AuthenticationError:
                    throttle.failure(tenant, ticket['email'])
                    factor_denied = True
                if not factor_denied:
                    self.db.execute('UPDATE ago_users SET password_hash=%s,session_version=session_version+1 WHERE tenant_id=%s AND id=%s',
                                    (encoded, tenant, actor.subject))
                result = {'credentials_changed': True}
            if not factor_denied:
                self.db.execute('UPDATE ago_identity_tickets SET used_at=clock_timestamp() WHERE id=%s', (ticket['id'],))
                self._audit(actor, 'identity.ticket.redeemed', {'ticket_id': str(ticket['id']), 'kind': ticket['kind']})
        if factor_denied:
            self.db.commit()
            raise AuthenticationError('Invalid credentials')
        return result

    def bind_sso(self, *, actor: Principal, user_id: str, subject: str) -> dict:
        UUID(user_id)
        if not 1 <= len(subject) <= 255:
            raise ValueError('Bounded provider subject required')
        provider = self.provider or OIDCProvider()
        with self.db.transaction():
            self._human(actor)
            if not self.db.execute('SELECT 1 FROM ago_users WHERE tenant_id=%s AND id=%s AND active=true',
                                    (actor.tenant_id, user_id)).fetchone():
                raise PermissionError('Same-tenant active user required')
            self.db.execute('INSERT INTO ago_sso_bindings(tenant_id,user_id,issuer,subject) VALUES(%s,%s,%s,%s)',
                            (actor.tenant_id, user_id, provider.config['issuer'], subject))
            self._audit(actor, 'sso.subject.bound', {'user_id': user_id, 'subject_sha256': hashlib.sha256(subject.encode()).hexdigest()})
        return {'user_id': user_id, 'bound': True}

    def begin_sso(self, *, tenant_id: str, browser_binding: str) -> dict:
        UUID(tenant_id)
        digest_token(browser_binding)
        provider = self.provider or OIDCProvider()
        state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(3))
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        with self.db.transaction():
            if not self.db.execute('SELECT 1 FROM ago_tenants WHERE id=%s', (tenant_id,)).fetchone():
                raise AuthenticationError('Invalid SSO authentication')
            self.db.execute('DELETE FROM ago_sso_states WHERE tenant_id=%s AND (expires_at<=clock_timestamp() OR consumed=true)', (tenant_id,))
            count = self.db.execute('SELECT count(*) AS count FROM ago_sso_states WHERE tenant_id=%s', (tenant_id,)).fetchone()['count']
            if count >= 100:
                raise AuthenticationError('SSO authentication capacity exceeded')
            self.db.execute('INSERT INTO ago_sso_states(state_hash,tenant_id,browser_hash,nonce,verifier_ciphertext) VALUES(%s,%s,%s,%s,%s)',
                (digest_token(state), tenant_id, digest_token(browser_binding), nonce, encrypt_factor(verifier, tenant_id, 'oidc-state')))
        return {'authorization_url': provider.authorization_url(state, nonce, challenge)}

    def finish_sso(self, *, state: str, browser_binding: str, code: str) -> Principal:
        provider = self.provider or OIDCProvider()
        # Claim/consume before any provider network request: failed exchanges cannot replay.
        with self.db.transaction():
            row = self.db.execute('''UPDATE ago_sso_states SET consumed=true WHERE state_hash=%s AND browser_hash=%s
                AND consumed=false AND expires_at>clock_timestamp() RETURNING *''',
                (digest_token(state), digest_token(browser_binding))).fetchone()
        if not row:
            raise AuthenticationError('Invalid SSO authentication')
        self.db.commit()
        tenant = str(row['tenant_id'])
        claims = provider.exchange(code, decrypt_factor(row['verifier_ciphertext'], tenant, 'oidc-state'), row['nonce'])
        with self.db.transaction():
            user = self.db.execute('''SELECT u.id,u.session_version FROM ago_sso_bindings b JOIN ago_users u
                ON u.tenant_id=b.tenant_id AND u.id=b.user_id
                WHERE b.tenant_id=%s AND b.issuer=%s AND b.subject=%s AND u.active=true''',
                (tenant, provider.config['issuer'], claims['sub'])).fetchone()
            if not user:
                raise AuthenticationError('Invalid SSO authentication')
            roles = self.db.execute('SELECT role FROM ago_user_roles WHERE tenant_id=%s AND user_id=%s ORDER BY role',
                                    (tenant, user['id'])).fetchall()
            actor = Principal(str(user['id']), tenant, tuple(r['role'] for r in roles), user['session_version'])
            self._audit(actor, 'sso.login.accepted')
        return actor

    def rotate_factors(self, *, actor: Principal, limit: int = 100) -> dict:
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError('Invalid rotation bound')
        with self.db.transaction():
            self._human(actor)
            current, _ = factor_keys()
            rows = self.db.execute('SELECT * FROM ago_mfa_factors WHERE tenant_id=%s AND ciphertext NOT LIKE %s ORDER BY user_id FOR UPDATE LIMIT %s',
                                    (actor.tenant_id, current+'.%', limit)).fetchall()
            for row in rows:
                user = str(row['user_id'])
                secret = decrypt_factor(row['ciphertext'], actor.tenant_id, user)
                self.db.execute('UPDATE ago_mfa_factors SET ciphertext=%s WHERE tenant_id=%s AND user_id=%s',
                                (encrypt_factor(secret, actor.tenant_id, user), actor.tenant_id, user))
            self._audit(actor, 'mfa.keys.reencrypted', {'count': len(rows)})
            self.db.execute('DELETE FROM ago_mfa_enrollments WHERE tenant_id=%s', (actor.tenant_id,))
            self.db.execute('DELETE FROM ago_sso_states WHERE tenant_id=%s', (actor.tenant_id,))
        return {'reencrypted': len(rows)}

    def create_handoff(self, *, actor: Principal, browser_binding: str) -> str:
        token = secrets.token_urlsafe(32)
        self.db.execute('INSERT INTO ago_sso_handoffs(token_hash,browser_hash,tenant_id,user_id,session_version) VALUES(%s,%s,%s,%s,%s)',
                        (digest_token(token), digest_token(browser_binding), actor.tenant_id, actor.subject, actor.session_version))
        return token

    def redeem_handoff(self, *, token: str, browser_binding: str) -> Principal:
        token_hash, browser_hash = digest_token(token), digest_token(browser_binding)
        with self.db.transaction():
            row = self.db.execute('DELETE FROM ago_sso_handoffs WHERE token_hash=%s AND browser_hash=%s AND expires_at>clock_timestamp() RETURNING *',
                                  (token_hash, browser_hash)).fetchone()
            if not row:
                raise AuthenticationError('Invalid SSO authentication')
            tenant, user = str(row['tenant_id']), str(row['user_id'])
            if not self.repositories.resolve(IdentityRepository).active(tenant, user, session_version=row['session_version']):
                raise AuthenticationError('Invalid SSO authentication')
            roles = self.db.execute('SELECT role FROM ago_user_roles WHERE tenant_id=%s AND user_id=%s ORDER BY role', (tenant, user)).fetchall()
        return Principal(user, tenant, tuple(r['role'] for r in roles), row['session_version'])
