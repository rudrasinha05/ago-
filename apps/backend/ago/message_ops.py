"""Explicit OS-authorized operator worker: only notification/event receipts."""
import argparse
import json
import os

from ago.backend_contracts import RepositoryScope
from ago.message_store import MessageStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tenant', required=True)
    parser.add_argument('--worker', required=True)
    parser.add_argument('--confirm', action='store_true')
    args = parser.parse_args()
    if not args.confirm:
        parser.error('Explicit operator confirmation required')
    import psycopg
    from psycopg.rows import dict_row
    try:
        with psycopg.connect(os.environ['AGO_POSTGRES_DSN'], row_factory=dict_row,
                             autocommit=True, connect_timeout=3) as db:
            store = RepositoryScope(db).resolve(MessageStore)
            delivered = failed = 0
            for row in store.claim(tenant_id=args.tenant, worker_id=args.worker):
                options = {'tenant_id': args.tenant, 'message_id': str(row['id']),
                           'lease_token': str(row['lease_token'])}
                if row['message_kind'] not in {'notification', 'event'}:
                    store.fail(**options, category='unregistered-handler')
                    failed += 1
                    continue
                try:
                    delivered += store.dispatch(**options, consumer='ago-receipt-v1',
                        handler=lambda connection, message: {'recorded': True, 'kind': message['message_kind']})
                except Exception:
                    store.fail(**options)
                    failed += 1
            print(json.dumps({'delivered': delivered, 'failed': failed}))
            return 0
    except Exception:
        print(json.dumps({'passed': False, 'error': 'Message maintenance failed'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
