"""Fixed-provider OIDC code+PKCE exchange and strict MFA ID-token verification."""
from __future__ import annotations

import hmac
import json
import os
import ssl
import time
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import httpx
import jwt

from ago.security import AuthenticationError
from ago.security_material import safe_https


class OIDCProvider:
    def __init__(self, config: dict | None = None):
        try:
            self.config = config or json.loads(os.environ['AGO_OIDC_CONFIG'])
            for key in ('issuer', 'authorization_endpoint', 'token_endpoint', 'redirect_uri'):
                safe_https(self.config[key])
            origin = urlsplit(self.config['issuer']).netloc
            if any(urlsplit(self.config[k]).netloc != origin for k in ('authorization_endpoint', 'token_endpoint')):
                raise ValueError('Provider endpoints must share configured issuer origin')
            if not 1 <= len(self.config['client_id']) <= 150:
                raise ValueError('Invalid OIDC client')
            if urlsplit(self.config['redirect_uri']).path != '/v1/security/sso/callback':
                raise ValueError('Exact callback URI required')
            raw = Path(self.config['jwks_file']).read_bytes()
            if len(raw) > 32768:
                raise ValueError('Signing keyset exceeds bounds')
            keys = json.loads(raw)['keys']
            if not 1 <= len(keys) <= 5:
                raise ValueError('Bounded pinned RSA keys required')
            self.keys = {}
            for key in keys:
                if (key.get('kty') != 'RSA' or key.get('alg', 'RS256') != 'RS256'
                        or key.get('use', 'sig') != 'sig' or 'd' in key or not key.get('kid')
                        or key['kid'] in self.keys):
                    raise ValueError('Public fixed-algorithm signing keys required')
                public = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
                if public.key_size < 2048:
                    raise ValueError('RSA key is too small')
                self.keys[key['kid']] = public
        except Exception as exc:
            raise AuthenticationError('SSO provider not configured') from exc

    def authorization_url(self, state: str, nonce: str, challenge: str) -> str:
        return self.config['authorization_endpoint'] + '?' + urlencode({
            'response_type': 'code', 'scope': 'openid', 'client_id': self.config['client_id'],
            'redirect_uri': self.config['redirect_uri'], 'state': state, 'nonce': nonce,
            'code_challenge': challenge, 'code_challenge_method': 'S256', 'max_age': '300'})

    def verify(self, token: str, nonce: str) -> dict:
        try:
            if len(token) > 8192:
                raise ValueError('Oversized ID token')
            header = jwt.get_unverified_header(token)
            if header.get('alg') != 'RS256':
                raise ValueError('Unapproved algorithm')
            claims = jwt.decode(token, self.keys[header['kid']], algorithms=['RS256'],
                audience=self.config['client_id'], issuer=self.config['issuer'],
                options={'require': ['iss', 'sub', 'aud', 'exp', 'iat', 'nonce', 'auth_time'], 'strict_aud': True})
            now = int(time.time())
            methods = claims.get('amr', [])
            if (not isinstance(claims['sub'], str) or not 1 <= len(claims['sub']) <= 255
                    or not isinstance(claims['nonce'], str) or not hmac.compare_digest(claims['nonce'], nonce)
                    or type(claims['auth_time']) is not int or not now-300 <= claims['auth_time'] <= now
                    or type(claims['iat']) is not int or type(claims['exp']) is not int
                    or not 0 < claims['exp']-claims['iat'] <= 3600
                    or not isinstance(methods, list)
                    or not ('mfa' in methods or {'pwd', 'otp'} <= set(methods))
                    or claims.get('azp', self.config['client_id']) != self.config['client_id']):
                raise ValueError('Fresh browser-bound MFA authentication required')
            return claims
        except Exception as exc:
            raise AuthenticationError('Invalid SSO authentication') from exc

    def exchange(self, code: str, verifier: str, nonce: str) -> dict:
        try:
            if not 1 <= len(code) <= 2048:
                raise ValueError('Bounded authorization code required')
            data = {'grant_type': 'authorization_code', 'code': code, 'code_verifier': verifier,
                    'client_id': self.config['client_id'], 'redirect_uri': self.config['redirect_uri']}
            secret = os.getenv('AGO_OIDC_CLIENT_SECRET')
            if secret:
                data['client_secret'] = secret
            context = ssl.create_default_context(cafile=self.config.get('ca_file'))
            with httpx.Client(verify=context, follow_redirects=False, trust_env=False, timeout=3) as client:
                with client.stream('POST', self.config['token_endpoint'], data=data) as response:
                    if response.status_code != 200:
                        raise ValueError('Token exchange failed')
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > 16384:
                            raise ValueError('Provider response exceeds bounds')
            return self.verify(json.loads(body)['id_token'], nonce)
        except Exception as exc:
            raise AuthenticationError('Invalid SSO authentication') from exc
