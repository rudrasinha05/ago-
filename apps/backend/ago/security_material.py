"""Verified external Vault KV-v2 reads and bounded session signing-key rotation."""
from __future__ import annotations

import json
import os
import re
import ssl
import stat
import time
from urllib.parse import urlsplit

import httpx

from ago.security import AuthenticationError, SessionTokens


def safe_https(url: str) -> str:
    value = urlsplit(url)
    if (value.scheme != 'https' or not value.hostname or value.username or value.password
            or value.query or value.fragment):
        raise ValueError('Explicit HTTPS endpoint required')
    return url


def private_file(path: str) -> str:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077
                or info.st_uid != os.getuid() or info.st_size > 32768):
            raise ValueError('Private owned bounded secret file required')
        with os.fdopen(descriptor, closefd=False) as source:
            return source.read(32769).strip()
    finally:
        os.close(descriptor)


def vault_material() -> dict:
    try:
        address = safe_https(os.environ['AGO_VAULT_URL']).rstrip('/')
        path = os.environ['AGO_VAULT_KV_PATH']
        if not re.fullmatch(r'[a-zA-Z0-9_-]+/data/[a-zA-Z0-9_/-]+', path) or '..' in path:
            raise ValueError('Explicit Vault KV-v2 data path required')
        token = private_file(os.environ['AGO_VAULT_TOKEN_FILE'])
        if not token or len(token) > 4096 or any(c.isspace() for c in token):
            raise ValueError('Invalid vault token')
        context = ssl.create_default_context(cafile=os.environ['AGO_VAULT_CA_FILE'])
        with httpx.Client(verify=context, follow_redirects=False, trust_env=False, timeout=3) as client:
            with client.stream('GET', address+'/v1/'+path, headers={'X-Vault-Token': token}) as response:
                if response.status_code != 200:
                    raise ValueError('Vault unavailable')
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > 32768:
                        raise ValueError('Vault response exceeds bounds')
        data = json.loads(body)['data']
        metadata = data['metadata']
        if metadata.get('destroyed') or metadata.get('deletion_time') or type(metadata.get('version')) is not int:
            raise ValueError('Invalid secret version')
        material = data['data']
        allowed = {'AGO_SESSION_SECRET', 'AGO_SESSION_KEYRING', 'AGO_POSTGRES_DSN', 'AGO_MFA_KEYS', 'AGO_OIDC_CLIENT_SECRET'}
        if (not isinstance(material, dict) or not {'AGO_SESSION_SECRET', 'AGO_SESSION_KEYRING', 'AGO_POSTGRES_DSN', 'AGO_MFA_KEYS'} <= material.keys()
                or set(material) - allowed or not all(isinstance(v, str) and v for v in material.values())):
            raise ValueError('Invalid secret bundle')
        return material
    except Exception as exc:
        raise AuthenticationError('Production secret provider unavailable') from exc


def bootstrap_security() -> None:
    if os.getenv('AGO_ENVIRONMENT', 'development').lower() == 'production':
        os.environ.update(vault_material())


class RotatingSessionTokens(SessionTokens):
    def __init__(self, keyring: str, *, now: int | None = None):
        try:
            data = json.loads(keyring)
            self.current = data['current']
            self.keys = data['keys']
            self._clock = int(time.time()) if now is None else now
            if not isinstance(self.keys, dict) or not 1 <= len(self.keys) <= 3 or self.current not in self.keys:
                raise ValueError('Invalid keyring')
            for identifier, key in self.keys.items():
                if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}', identifier) or len(key['secret'].encode()) < 48:
                    raise ValueError('Invalid signing key')
                if identifier != self.current and (type(key.get('verify_until')) is not int or key['verify_until'] > self._clock + 900):
                    raise ValueError('Retired key overlap exceeds session TTL')
            super().__init__(self.keys[self.current]['secret'])
        except (KeyError, TypeError, ValueError) as exc:
            raise AuthenticationError('Signing keyring unavailable') from exc

    def issue(self, principal, *, now=None):
        return self.current + '.' + super().issue(principal, now=now)

    def verify(self, token, *, now=None):
        try:
            identifier, body = token.split('.', 1)
            key = self.keys[identifier]
            current = int(time.time()) if now is None else now
            if identifier != self.current and current >= key['verify_until']:
                raise ValueError('Retired key expired')
            return SessionTokens(key['secret']).verify(body, now=now)
        except (KeyError, TypeError, ValueError) as exc:
            raise AuthenticationError('Invalid session') from exc
