"""Generate the Python wheel console adapters from canonical JS workspaces."""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sync(check=False):
    sources = {
        'core.js': (ROOT/'packages/sdk/session.js').read_text(),
        'views.js': (ROOT/'packages/ui/compat/views.js').read_text().replace('"@ago/sdk/session"', '"./core.js"'),
        'actions.js': (ROOT/'packages/ui/compat/actions.js').read_text().replace('"@ago/sdk/session"', '"./core.js"'),
        'styles.css': (ROOT/'packages/ui/workspace.css').read_text(),
    }
    errors = []
    for name, content in sources.items():
        destination = ROOT/'apps/backend/ago/console'/name
        if check:
            if destination.read_text() != content:
                errors.append(name)
        else:
            destination.write_text(content)
    if errors:
        raise SystemExit('Console adapter drift: '+', '.join(errors))
    print('Canonical UI/SDK console adapters verified' if check else 'Console adapters generated')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    sync(parser.parse_args().check)
