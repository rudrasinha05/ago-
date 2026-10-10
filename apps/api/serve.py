"""Canonical API shell forwards to the existing AGO application."""
import argparse

import uvicorn

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('Port must be between 1024 and 65535')
    uvicorn.run('ago.main:app', host='127.0.0.1', port=args.port, proxy_headers=False)
