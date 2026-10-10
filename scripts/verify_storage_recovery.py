"""Disposable CI-only PostgreSQL + actual semantic model + private byte recovery.

Requires test/restore DSNs; never targets a production database. Writes are
deliberately confined to disposable CI directories and an empty drill target.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

from ago.bootstrap import bootstrap
from ago.database_store import DatabaseStore
from ago.knowledge_store import KnowledgeStore
from ago.provision import add_reviewer
from ago.release_ops import create_backup, restore_drill
from ago.security import Principal
from ago.storage_adapters import PrivateObjects


def run() -> dict:
    import psycopg
    from psycopg.rows import dict_row
    source = os.environ['AGO_TEST_POSTGRES_DSN']
    target = os.environ['AGO_RESTORE_TEST_DSN']
    # Existing release restore tooling additionally enforces endpoint isolation.
    if source != os.environ['AGO_POSTGRES_DSN'] or not target.endswith('/ago_restore_drill'):
        raise ValueError('Disposable source and isolated drill target required')
    root = Path('/tmp') / ('ago-s7-drill-' + str(uuid4()))
    root.mkdir(mode=0o700)
    objects = root / 'objects'
    objects.mkdir(mode=0o700)
    backup, recovered = root / 'object-backup', root / 'recovered-objects'
    dump = root / 'database.dump'
    with psycopg.connect(source, row_factory=dict_row, autocommit=True) as db:
        tenant, founder = bootstrap(db, organization='Section 7 disposable recovery',
            email='recovery-founder@example.test', password='disposable-founder-password-123')
        reviewer = add_reviewer(db, tenant_id=tenant, email='recovery-reviewer@example.test',
                                password='disposable-reviewer-password-123')
        author = Principal(founder, tenant, ('founder',))
        review_actor = Principal(reviewer, tenant, ('reviewer',))
        knowledge = KnowledgeStore(db)
        nodes = []
        for label in ('A dog is a loyal domestic pet', 'Databases maintain durable transaction logs'):
            node = knowledge.propose(actor=author, kind='fact', label=label,
                                      statement=label, source_ref='internal:recovery:' + str(len(nodes)))
            knowledge.review(actor=review_actor, node_id=node, approve=True,
                              note='Independent disposable evidence review')
            nodes.append(node)
        knowledge.relate(actor=author, from_id=nodes[0], to_id=nodes[1], relation='references')
        store = DatabaseStore(db, objects=PrivateObjects(objects))
        assert store.rebuild_index(tenant_id=tenant)['indexed'] == 2
        content = b'Disposable private recovery evidence\x00\xff'
        upload = store.upload(actor=author, filename='evidence.bin',
                               media_type='application/octet-stream', content=content)
        assert store.backup_objects(tenant_id=tenant, destination=str(backup))['backed_up'] == 1
    # No application writers run in this job: object and database backups are coordinated.
    create_backup(source, dump, confirmed=True)
    with psycopg.connect(source.rsplit('/', 1)[0] + '/postgres', autocommit=True) as admin:
        admin.execute('CREATE DATABASE ago_restore_drill')
    assert restore_drill(source, target, dump, confirmed=True)['restored'] is True
    with psycopg.connect(target, row_factory=dict_row, autocommit=True) as restored_db:
        store = DatabaseStore(restored_db)
        assert store.restore_objects(tenant_id=tenant, source=str(backup),
                                      destination=str(recovered))['verified']
        store = DatabaseStore(restored_db, objects=PrivateObjects(recovered))
        assert store.download(tenant_id=tenant, object_id=upload['id'])[1] == content
        graph = store.graph(tenant_id=tenant, root_id=nodes[0])
        assert len(graph['nodes']) == 2 and len(graph['edges']) == 1
        result = store.search(tenant_id=tenant, query='A faithful household animal companion')
        assert result['indexed'] == 2 and result['results'][0]['id'] == nodes[0]
        # A mismatched metadata/manifest pair cannot be installed during recovery.
        manifest_path = backup / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['objects'][0]['sha256'] = '0' * 64
        manifest_path.write_text(json.dumps(manifest))
        try:
            store.restore_objects(tenant_id=tenant, source=str(backup),
                                  destination=str(root / 'invalid-restore'))
        except ValueError:
            pass
        else:
            raise AssertionError('Inconsistent restored metadata accepted')
    return {'database_restored': True, 'objects_recovered': 1, 'graph_recovered': True,
            'actual_semantic_index_recovered': True, 'mismatched_manifest_rejected': True}


if __name__ == '__main__':
    print(json.dumps(run()))
