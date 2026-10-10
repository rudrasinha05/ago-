"""Versioned transport values; no envelope conveys authorization."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from uuid import UUID

KINDS = frozenset({'command', 'event', 'query', 'notification', 'approval'})
RESERVED = frozenset({'authorized', 'approved', 'password', 'access_token', 'secret', 'roles'})


@dataclass(frozen=True)
class MessageEnvelope:
    kind: str
    name: str
    tenant_id: str
    actor_id: str
    correlation_id: str
    operation_key: str
    ordering_key: str
    payload_json: str
    version: int = 1

    def __post_init__(self):
        for value in (self.tenant_id, self.actor_id, self.correlation_id):
            UUID(value)
        if (self.kind not in KINDS or type(self.version) is not int or self.version != 1
                or not re.fullmatch(r'[a-z][a-z0-9_.-]{2,99}', self.name)
                or not 1 <= len(self.operation_key) <= 150
                or not 1 <= len(self.ordering_key) <= 150):
            raise ValueError('Invalid communication envelope')
        if len(self.payload_json.encode()) > 8192:
            raise ValueError('Message payload exceeds limits')
        data = json.loads(self.payload_json)
        if not isinstance(data, dict):
            raise ValueError('Message payload must be an object')
        def check(value, depth=0):
            if depth > 8:
                raise ValueError('Message nesting exceeds limits')
            if isinstance(value, dict):
                if any(str(key).lower() in RESERVED for key in value):
                    raise ValueError('Message cannot inject authority or credentials')
                for item in value.values():
                    check(item, depth + 1)
            elif isinstance(value, list):
                for item in value:
                    check(item, depth + 1)
            elif isinstance(value, float):
                import math
                if not math.isfinite(value):
                    raise ValueError('Nonfinite message value')
        check(data)
        if self.kind == 'approval' and (
            set(data) != {'request_id', 'status'} or data['status'] != 'requested'
        ):
            raise ValueError('Approval envelopes can only coordinate a pending request')
        if self.kind == 'approval':
            UUID(data['request_id'])

    def digest(self) -> str:
        body = {'kind': self.kind, 'name': self.name, 'tenant_id': self.tenant_id,
                'actor_id': self.actor_id, 'operation_key': self.operation_key,
                'ordering_key': self.ordering_key, 'payload': json.loads(self.payload_json),
                'version': self.version}
        return hashlib.sha256(json.dumps(body, sort_keys=True, allow_nan=False).encode()).hexdigest()
