"""Trusted optional localhost opportunity watcher; never sends email or spends money.

Run from apps/backend:
 python ../../scripts/opportunity_scan.py --tenant-id UUID --once
 python ../../scripts/opportunity_scan.py --tenant-id UUID --interval-seconds 3600
Only keeps making progress while this process and localhost PostgreSQL run.
"""
import argparse
import json
import os
import time
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from ago.company_chat import CompanyChat
from ago.local_ops import local_database


def main():
    parser=argparse.ArgumentParser(description='AGO idle-company idea watcher')
    parser.add_argument('--tenant-id',required=True)
    parser.add_argument('--once',action='store_true')
    parser.add_argument('--interval-seconds',type=int,default=3600)
    args=parser.parse_args()
    tenant=str(UUID(args.tenant_id))
    if not 300<=args.interval_seconds<=86400:
        parser.error('Polling interval must be between 300 and 86400 seconds')
    dsn=os.getenv('AGO_POSTGRES_DSN','')
    if os.getenv('AGO_ENVIRONMENT','development') not in ('development','test','testing') or not local_database(dsn):
        parser.error('Only configured localhost development/test PostgreSQL is supported')
    while True:
        with psycopg.connect(dsn,row_factory=dict_row,autocommit=True,connect_timeout=5) as db:
            report=CompanyChat(db).scan_opportunities(tenant)
        print(json.dumps(report,sort_keys=True),flush=True)
        if args.once:
            break
        time.sleep(args.interval_seconds)


if __name__=='__main__':
    main()
