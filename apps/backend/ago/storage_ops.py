"""Explicit operator maintenance; never imported by HTTP composition."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from ago.backend_contracts import RepositoryScope
from ago.database_store import DatabaseStore
from ago.storage_adapters import prepare_model


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prepare = sub.add_parser('prepare-model')
    prepare.add_argument('--directory', required=True)
    prepare.add_argument('--confirm', action='store_true')
    for name in ('rebuild-index', 'expire', 'backup-objects', 'restore-objects', 'verify-objects'):
        command = sub.add_parser(name)
        command.add_argument('--tenant', required=True)
        if name == 'backup-objects':
            command.add_argument('--destination', required=True)
        if name == 'restore-objects':
            command.add_argument('--source', required=True)
            command.add_argument('--destination', required=True)
        if name in ('backup-objects', 'restore-objects'):
            command.add_argument('--offline', action='store_true',
                                 help='Confirm application writers are stopped for coordinated recovery')
        if name != 'verify-objects':
            command.add_argument('--confirm', action='store_true')
    args = parser.parse_args()
    try:
        if args.command != 'verify-objects' and not args.confirm:
            raise PermissionError('Maintenance requires explicit operator confirmation')
        if args.command == 'prepare-model':
            result = prepare_model(Path(args.directory).absolute())
        else:
            import psycopg
            from psycopg.rows import dict_row
            with psycopg.connect(os.environ['AGO_POSTGRES_DSN'], row_factory=dict_row,
                                 autocommit=True, connect_timeout=3) as db:
                store = RepositoryScope(db).resolve(DatabaseStore)
                if args.command == 'rebuild-index':
                    result = store.rebuild_index(tenant_id=args.tenant)
                elif args.command == 'expire':
                    result = store.expire(tenant_id=args.tenant, limit=1000)
                elif args.command in ('backup-objects', 'restore-objects'):
                    if not args.offline:
                        raise PermissionError('Coordinated recovery requires stopped application writers')
                    if args.command == 'backup-objects':
                        result = store.backup_objects(tenant_id=args.tenant, destination=args.destination)
                    else:
                        result = store.restore_objects(tenant_id=args.tenant, source=args.source,
                                                       destination=args.destination)
                else:
                    rows = store.object_manifest(tenant_id=args.tenant)
                    for row in rows:
                        store._bytes().read(args.tenant, row['id'], row['sha256'], row['bytes'])
                    result = {'verified': True, 'objects': len(rows)}
        print(json.dumps(result))
        return 0
    except Exception:
        # Provider details, paths, DSNs and documents stay out of operator/CI output.
        print(json.dumps({'passed': False, 'error': 'Storage maintenance failed'}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
