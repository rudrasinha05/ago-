"""RFC 6238 factors and tenant/user-bound authenticated secret encryption."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import struct
import time

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ago.security import AuthenticationError


def digest_token(token: str) -> str:
    if not isinstance(token, str) or not 20 <= len(token) <= 256:
        raise AuthenticationError('Invalid authentication material')
    return hashlib.sha256(token.encode()).hexdigest()


def factor_keys() -> tuple[str, dict[str, bytes]]:
    try:
        data = json.loads(os.environ['AGO_MFA_KEYS'])
        keys = data['keys']
        current = data['current']
        if not isinstance(keys, dict) or not 1 <= len(keys) <= 3 or current not in keys:
            raise ValueError('Invalid keyring')
        decoded = {}
        for identifier, value in keys.items():
            if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}', identifier):
                raise ValueError('Invalid key identity')
            key = base64.b64decode(value, altchars=b'-_', validate=True)
            if len(key) != 32:
                raise ValueError('Invalid key length')
            decoded[identifier] = key
        return current, decoded
    except (KeyError, TypeError, ValueError) as exc:
        raise AuthenticationError('Factor encryption not configured') from exc


def encrypt_factor(secret: str, tenant: str, user: str) -> str:
    current, keys = factor_keys()
    nonce = secrets.token_bytes(12)
    aad = f'ago:factor:v1:{tenant}:{user}'.encode()
    blob = nonce + AESGCM(keys[current]).encrypt(nonce, secret.encode(), aad)
    return current + '.' + base64.urlsafe_b64encode(blob).decode()


def decrypt_factor(ciphertext: str, tenant: str, user: str) -> str:
    try:
        _, keys = factor_keys()
        identifier, encoded = ciphertext.split('.', 1)
        blob = base64.b64decode(encoded, altchars=b'-_', validate=True)
        if len(blob) > 1024 or len(blob) < 29:
            raise ValueError('Invalid encrypted factor')
        return AESGCM(keys[identifier]).decrypt(blob[:12], blob[12:],
            f'ago:factor:v1:{tenant}:{user}'.encode()).decode()
    except Exception as exc:
        raise AuthenticationError('Factor material unavailable') from exc


def totp(secret: str, step: int) -> str:
    key = base64.b32decode(secret, casefold=False)
    digest = hmac.new(key, struct.pack('>Q', step), hashlib.sha1).digest()
    offset = digest[-1] & 15
    value = struct.unpack('>I', digest[offset:offset+4])[0] & 0x7fffffff
    return f'{value % 1000000:06d}'


def factor_step(secret: str, code: str, last_step: int = -1, *, now: int | None = None) -> int:
    if not isinstance(code, str) or not re.fullmatch(r'[0-9]{6}', code):
        raise AuthenticationError('Invalid credentials')
    current = (int(time.time()) if now is None else now) // 30
    for step in (current, current-1, current+1):
        if step >= 0 and step > last_step and hmac.compare_digest(totp(secret, step), code):
            return step
    raise AuthenticationError('Invalid credentials')
