"""Private bytes, offline CPU embeddings and optional non-authoritative cache.

No adapter starts a service or downloads a model on a request. Operator-owned
directories must be private; byte access uses no-follow directory descriptors.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import shutil
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from uuid import UUID, uuid4

MAX_BYTES = 524288
MODEL = 'BAAI/bge-small-en-v1.5'
DIMENSIONS = 384


class StorageUnavailable(RuntimeError):
    """Provider/configuration/integrity failure; never expose paths or secrets."""


def normalized(values) -> list[float]:
    try:
        vector = [float(v) for v in values]
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError('Invalid embedding') from exc
    if len(vector) != DIMENSIONS or not all(math.isfinite(v) for v in vector):
        raise ValueError('Invalid embedding dimensions or values')
    norm = math.sqrt(sum(v * v for v in vector))
    if not math.isfinite(norm) or norm <= 0:
        raise ValueError('Embedding must have finite nonzero magnitude')
    return [v / norm for v in vector]


class PrivateObjects:
    def __init__(self, root: str | Path | None = None):
        if os.name != 'posix':
            raise StorageUnavailable('Private objects require the Linux service runtime')
        configured = root or os.getenv('AGO_OBJECTS_DIR')
        if not configured:
            raise StorageUnavailable('Private object storage not configured')
        self.root = Path(configured).absolute()
        if self.root.is_symlink() or not self.root.is_dir():
            raise StorageUnavailable('Private object directory unavailable')
        if self.root.stat().st_mode & 0o077:
            raise StorageUnavailable('Private object directory requires owner-only permissions')
        # Parent symlinks are also forbidden; configuration is operator controlled.
        if self.root.resolve() != self.root:
            raise StorageUnavailable('Private object directory must be canonical')

    @contextmanager
    def _directory(self, tenant: str, *, create: bool = False):
        tenant = str(UUID(tenant))
        root_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        child = None
        try:
            if create:
                try:
                    os.mkdir(tenant, 0o700, dir_fd=root_fd)
                except FileExistsError:
                    pass
            child = os.open(tenant, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=root_fd)
            yield child
        finally:
            if child is not None:
                os.close(child)
            os.close(root_fd)

    def write(self, tenant: str, identifier: str, content: bytes) -> None:
        identifier = str(UUID(identifier))
        if not 1 <= len(content) <= MAX_BYTES:
            raise ValueError('Object must contain 1 to 524288 bytes')
        temporary = '.pending-' + str(uuid4())
        with self._directory(tenant, create=True) as directory:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=directory)
            try:
                with os.fdopen(fd, 'wb') as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
                # Atomic, exclusive installation: never overwrite an existing object.
                os.link(temporary, identifier, src_dir_fd=directory, dst_dir_fd=directory,
                        follow_symlinks=False)
                os.fsync(directory)
            finally:
                os.unlink(temporary, dir_fd=directory)

    def read(self, tenant: str, identifier: str, digest: str, size: int) -> bytes:
        identifier = str(UUID(identifier))
        try:
            with self._directory(tenant) as directory:
                fd = os.open(identifier, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
                with os.fdopen(fd, 'rb') as handle:
                    import stat
                    if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                        raise StorageUnavailable('Object integrity unavailable')
                    content = handle.read(MAX_BYTES + 1)
        except OSError as exc:
            raise StorageUnavailable('Object unavailable') from exc
        if len(content) != size or not 1 <= size <= MAX_BYTES or not hmac.compare_digest(
            hashlib.sha256(content).hexdigest(), digest
        ):
            raise StorageUnavailable('Object integrity unavailable')
        return content

    def remove(self, tenant: str, identifier: str) -> None:
        try:
            with self._directory(tenant) as directory:
                os.unlink(str(UUID(identifier)), dir_fd=directory)
                os.fsync(directory)
        except FileNotFoundError:
            pass


def _files(root: Path) -> dict[str, str]:
    files = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise StorageUnavailable('Model symlinks forbidden')
        if path.is_file() and path.name != 'ago-model.json':
            files[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def prepare_model(root: Path) -> dict:
    """Explicit operator-only network preparation, immutable fingerprint manifest."""
    from fastembed import TextEmbedding
    if root.exists():
        raise ValueError('Model preparation requires a new directory')
    root.mkdir(mode=0o700, parents=True)
    downloads = root / 'download'
    encoder = TextEmbedding(MODEL, cache_dir=str(downloads), threads=1)
    normalized(next(encoder.embed(['Model integrity probe'])))
    # HF snapshots use symlinks; install a self-contained, no-symlink runtime copy.
    shutil.copytree(encoder.model._model_dir, root / 'weights', symlinks=False)
    shutil.rmtree(downloads)
    files = _files(root)
    fingerprint = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    manifest = {'model': MODEL, 'dimensions': DIMENSIONS, 'files': files,
                'fingerprint': fingerprint}
    (root / 'ago-model.json').write_text(json.dumps(manifest, sort_keys=True))
    return {'prepared': True, 'model_id': MODEL + ':' + fingerprint}


class OfflineEncoder:
    def __init__(self, root: Path):
        try:
            manifest = json.loads((root / 'ago-model.json').read_text())
            actual = _files(root)
            fingerprint = hashlib.sha256(json.dumps(actual, sort_keys=True).encode()).hexdigest()
            if (manifest['model'] != MODEL or manifest['dimensions'] != DIMENSIONS
                    or manifest['files'] != actual or not actual
                    or manifest['fingerprint'] != fingerprint):
                raise ValueError('Model integrity mismatch')
            from fastembed import TextEmbedding
            self.encoder = TextEmbedding(MODEL, cache_dir=str(root), threads=1,
                                         local_files_only=True,
                                         specific_model_path=str(root / 'weights'))
            self.model_id = MODEL + ':' + fingerprint
        except Exception as exc:
            raise StorageUnavailable('Prepared semantic model unavailable') from exc

    def embed(self, text: str, *, query: bool = False) -> list[float]:
        if not 1 <= len(text.strip()) <= 14000:
            raise ValueError('Embedding input is outside limits')
        try:
            method = self.encoder.query_embed if query else self.encoder.passage_embed
            return normalized(next(method(text)))
        except Exception as exc:
            raise StorageUnavailable('Semantic encoder unavailable') from exc


@lru_cache(maxsize=2)
def _encoder(root: str, manifest_digest: str) -> OfflineEncoder:
    return OfflineEncoder(Path(root))


def offline_encoder() -> OfflineEncoder:
    configured = os.getenv('AGO_EMBEDDING_DIR')
    if not configured:
        raise StorageUnavailable('Prepared semantic model not configured')
    root = Path(configured).absolute()
    try:
        if root.resolve() != root:
            raise ValueError('Noncanonical model directory')
        digest = hashlib.sha256((root / 'ago-model.json').read_bytes()).hexdigest()
        return _encoder(str(root), digest)
    except OSError as exc:
        raise StorageUnavailable('Prepared semantic model unavailable') from exc


class TraversalCache:
    """Only signed results under tenant/version/request-specific keys, 60s TTL."""
    def __init__(self):
        self.client = None
        self.secret = os.getenv('AGO_SESSION_SECRET', '').encode()
        url = os.getenv('AGO_GRAPH_REDIS_URL')
        if url and len(self.secret) >= 32:
            try:
                import redis
                from redis.retry import Retry
                from redis.backoff import NoBackoff
                self.client = redis.Redis.from_url(
                    url, socket_timeout=0.2, socket_connect_timeout=0.2,
                    retry=Retry(NoBackoff(), 0), max_connections=2)
            except Exception:
                pass

    def key(self, tenant: str, version: int, request: tuple) -> str:
        fingerprint = hashlib.sha256(json.dumps(request).encode()).hexdigest()
        return f'ago:graph:v1:{UUID(tenant)}:{version}:{fingerprint}'

    def get(self, key: str) -> dict | None:
        if self.client is None:
            return None
        try:
            raw = self.client.get(key)
            if not raw or len(raw) > 1024 * 1024:
                return None
            signature, body = raw.split(b'\n', 1)
            expected = hmac.new(self.secret, key.encode() + body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature.decode(), expected):
                return None
            payload = json.loads(body)
            return payload if isinstance(payload, dict) else None
        except Exception:
            return None
        finally:
            self.client.close()

    def put(self, key: str, value: dict) -> None:
        if self.client is None:
            return
        try:
            body = json.dumps(value, sort_keys=True, default=str).encode()
            if len(body) > 1024 * 1024 - 65:
                return
            signature = hmac.new(self.secret, key.encode() + body, hashlib.sha256).hexdigest()
            self.client.setex(key, 60, signature.encode() + b'\n' + body)
        except Exception:
            pass
        finally:
            self.client.close()
