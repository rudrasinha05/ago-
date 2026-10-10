"""Serve and verify all three real Next.js exports over isolated loopback HTTP."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
for app, title in [('web', 'AGO Workspace'), ('admin', 'AGO Administration'),
                   ('docs', 'AGO Architecture')]:
    folder = ROOT / 'apps' / app / 'out'
    if not (folder / 'index.html').is_file():
        raise SystemExit(f'Missing actual build export: {app}')
    handler = partial(SimpleHTTPRequestHandler, directory=str(folder))
    with ThreadingHTTPServer(('127.0.0.1', 0), handler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urlopen(f'http://127.0.0.1:{server.server_port}/', timeout=5) as response:
                html = response.read().decode()
                assert response.status == 200 and title in html
                assert 'Open existing Control Center' in html
                assert 'http://127.0.0.1:8000/console/' in html
            print(f'{app}: real exported homepage served and verified')
        finally:
            server.shutdown()
            thread.join(timeout=5)
