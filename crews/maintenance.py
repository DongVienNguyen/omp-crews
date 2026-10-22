"""At most one retention pass per day; never compact in a tool/worker request."""
import sqlite3
import time
from contextlib import closing
from . import storage


def run(state):
    root = storage._root(state)
    if not storage._retention(root)['auto_cleanup']:
        return {'skipped': 'disabled'}
    with closing(sqlite3.connect(root / 'runs.sqlite', timeout=1)) as db:
        with db:
            db.execute('CREATE TABLE IF NOT EXISTS storage_maintenance (id INTEGER PRIMARY KEY, attempted REAL)')
            db.execute('BEGIN IMMEDIATE')
            previous = db.execute('SELECT attempted FROM storage_maintenance WHERE id=1').fetchone()
            if previous and time.time() - previous[0] < 86400:
                return {'skipped': 'throttled'}
            db.execute('INSERT OR REPLACE INTO storage_maintenance VALUES(1,?)', (time.time(),))
    # Cleanup rechecks run/admission safety under its own write transaction.
    return storage.dispatch({'operation': 'cleanup', 'dry_run': False}, state)
