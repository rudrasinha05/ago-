"""Dedicated CPU ONNX gate, never substituted by hash/lexical/test vectors."""
import os
import shutil
from pathlib import Path

import pytest

from ago.storage_adapters import OfflineEncoder, StorageUnavailable


def test_actual_model_load_and_semantics_without_any_model_network(monkeypatch, tmp_path):
    import fastembed.common.model_management as management
    def forbidden(*args, **kwargs):
        raise AssertionError('Request-time model network access forbidden')
    monkeypatch.setattr(management, 'model_info', forbidden)
    monkeypatch.setattr(management, 'snapshot_download', forbidden)
    root = Path(os.environ['AGO_EMBEDDING_DIR'])
    model = OfflineEncoder(root)
    dog = model.embed('A dog is a loyal domestic pet.')
    database = model.embed('An SQL database stores durable transaction logs.')
    query = model.embed('A faithful household animal companion', query=True)
    assert len(query) == len(dog) == len(database) == 384
    assert sum(a*b for a,b in zip(query, dog)) > sum(a*b for a,b in zip(query, database)) + 0.1
    corrupt = tmp_path / 'corrupt-model'
    shutil.copytree(root, corrupt)
    config = next((corrupt / 'weights').rglob('config.json'))
    config.write_text('{}')
    with pytest.raises(StorageUnavailable):
        OfflineEncoder(corrupt)
