"""Run: python check_storage.py. All writes stay inside temporary directories."""
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
from unittest.mock import patch

from crews.storage import DAY, SUMMARY_SCHEMA, dispatch

NOW = time.time()


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*')
            if p.is_file() and not p.is_symlink()}


def setup(root):
    root.mkdir()
    db = sqlite3.connect(root / 'runs.sqlite')
    db.executescript('''
      CREATE TABLE runs(id TEXT PRIMARY KEY,project TEXT,session TEXT,created REAL,plan TEXT);
      CREATE TABLE calls(run TEXT,role TEXT,digest TEXT,status TEXT,result TEXT,PRIMARY KEY(run,role));
      CREATE TABLE attempts(run TEXT,role TEXT,escalations INTEGER,repairs INTEGER,PRIMARY KEY(run,role));
      CREATE TABLE tickets(run TEXT,role TEXT,token TEXT,PRIMARY KEY(run,role));
      CREATE TABLE admissions(token TEXT PRIMARY KEY,run TEXT,role TEXT,project TEXT,session TEXT,expires REAL,call TEXT);
      CREATE TABLE receipts(token TEXT PRIMARY KEY,payload TEXT);
    ''')
    db.execute(SUMMARY_SCHEMA)
    db.commit()
    return db


def run(db, root, number, days=10, status='completed', observation=None):
    rid = f'{number:032x}'
    target = root / 'records' / rid / 'roles' / 'worker' / 'result.md'
    target.parent.mkdir(parents=True)
    target.write_text('sensitive result', encoding='utf-8')
    os.utime(target, (NOW - 3 * DAY, NOW - 3 * DAY))
    cell = {'role_id': 'worker', 'policy_combo': 'Small', 'model': 'model', 'reasoning_effort': 'low',
            'prompt': 'SECRET PROMPT', 'source': 'SECRET SOURCE',
            'classification': {'learning': {'observation_id': observation}}}
    plan = {'waves': [{'calls': [cell]}], 'records': {'worker': str(target)}}
    db.execute('INSERT INTO runs VALUES(?,?,?,?,?)', (rid, '/project', 'session', NOW - days * DAY, json.dumps(plan)))
    result = {'native': {'usage': {'input': 11, 'output': 12, 'prompt': 999, 'bad': 'SECRET'}, 'durationMs': 25},
              'fingerprints': {'SECRET': 'SECRET'}, 'commands': ['SECRET']}
    db.execute('INSERT INTO calls VALUES(?,?,?,?,?)', (rid, 'worker', 'SECRET', status, json.dumps(result)))
    db.execute('INSERT INTO attempts VALUES(?,?,?,?)', (rid, 'worker', 2, 1))
    return rid, target


def admission(db, rid, number, expires):
    token = f'{number:032x}'
    db.execute('INSERT INTO admissions VALUES(?,?,?,?,?,?,?)', (token, rid, 'worker', '/project', 'session', expires, '{}'))
    db.execute('INSERT INTO tickets VALUES(?,?,?)', (rid, 'worker', token))
    db.execute('INSERT INTO receipts VALUES(?,?)', (token, json.dumps({'run': rid, 'prompt': 'SECRET'})))
    return token


def legacy(root, token, rid, expires):
    for area in ('tickets', 'wire'):
        (root / area).mkdir(exist_ok=True)
    (root / 'tickets' / (token + '.json')).write_text(json.dumps({'token': token, 'run': rid, 'expires': expires}))
    (root / 'wire' / (token + '.json')).write_text('{}')


def expect_value_error(fn):
    try:
        fn()
    except ValueError:
        return
    raise AssertionError('expected ValueError')


def check():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        missing = base / 'missing'
        assert dispatch({'operation': 'status'}, missing)['database']['counts']['runs'] == 0
        assert dispatch({'operation': 'cleanup'}, missing)['dry_run']
        assert not missing.exists()
        root = base / 'state'
        db = setup(root)
        old, record = run(db, root, 1)
        fresh, fresh_record = run(db, root, 2, days=.5, status='admitted')
        live, live_record = run(db, root, 3)
        live_token = admission(db, live, 103, NOW + DAY)
        labeled, _ = run(db, root, 4, observation='labeled')
        family, _ = run(db, root, 5, observation='family')
        legacy_run, _ = run(db, root, 6)
        legacy(root, f'{106:032x}', legacy_run, NOW + DAY)
        stale_token = admission(db, old, 101, NOW - 7200)
        legacy(root, stale_token, old, NOW - 7200)
        grace = f'{107:032x}'
        legacy(root, grace, f'{999:032x}', NOW - 60)
        db.commit()
        db.close()
        learning = sqlite3.connect(root / 'learning.sqlite')
        learning.executescript('''CREATE TABLE observations(id TEXT,project TEXT,signature TEXT,policy TEXT);
          CREATE TABLE labels(observation_id TEXT);
          CREATE TABLE rules(project TEXT,signature TEXT,policy TEXT,state TEXT);
          INSERT INTO observations VALUES('labeled','p','a','b'),('family','p','c','d');
          INSERT INTO labels VALUES('labeled');
          INSERT INTO rules VALUES('p','c','d','candidate');''')
        learning.commit()
        learning.close()
        (root / 'learning.key').write_text('do not mutate')
        before = snapshot(root)
        status = dispatch({'operation': 'status'}, root)
        assert status['database']['counts']['runs'] == 6
        assert status['database']['page_count'] > 0
        preview = dispatch({'operation': 'cleanup'}, root)
        assert preview['archived_runs'] == [old]
        assert {fresh, live, labeled, family, legacy_run} <= set(preview['protected_runs'])
        assert snapshot(root) == before
        result = dispatch({'operation': 'cleanup', 'dry_run': False}, root)
        assert result['archived_runs'] == [old]
        assert not record.exists() and fresh_record.exists() and live_record.exists()
        assert (root / 'tickets' / (grace + '.json')).exists()
        assert not (root / 'tickets' / (stale_token + '.json')).exists()
        assert (root / 'learning.sqlite').read_bytes() == before['learning.sqlite']
        assert (root / 'learning.key').read_bytes() == before['learning.key']
        db = sqlite3.connect(root / 'runs.sqlite')
        assert db.execute('SELECT count(*) FROM runs WHERE id=?', (old,)).fetchone()[0] == 0
        for table in ('calls', 'attempts', 'tickets', 'admissions'):
            assert db.execute('SELECT count(*) FROM ' + table + ' WHERE run=?', (old,)).fetchone()[0] == 0
        assert db.execute('SELECT count(*) FROM receipts WHERE token=?', (stale_token,)).fetchone()[0] == 0
        raw = db.execute('SELECT summary FROM run_summaries WHERE run=?', (old,)).fetchone()[0]
        assert 'SECRET' not in raw and 'prompt' not in raw and 'source' not in raw and 'fingerprint' not in raw
        summary = json.loads(raw)
        assert summary['roles'][0]['usage'] == {'input': 11, 'output': 12}
        assert summary['attempts'] == {'escalations': 2, 'repairs': 1}
        assert db.execute('SELECT escalations,repairs FROM attempts WHERE run=?', (live,)).fetchone() == (2, 1)
        db.close()
        expect_value_error(lambda: dispatch({'operation': 'compact'}, root))

        capped = base / 'capped'
        db = setup(capped)
        ids = [run(db, capped, n, days=n)[0] for n in (8, 9, 10, 100)]
        active, _ = run(db, capped, 111, days=.25)
        db.commit()
        db.close()
        (capped / 'storage.json').write_text(json.dumps({'max_runs': 2}))
        result = dispatch({'operation': 'cleanup', 'dry_run': False}, capped)
        db = sqlite3.connect(capped / 'runs.sqlite')
        assert {r[0] for r in db.execute('SELECT run FROM run_summaries')} == set(ids[:2])
        assert db.execute('SELECT id FROM runs').fetchall() == [(active,)]
        db.close()
        assert set(result['trimmed_summaries']) == set(ids[2:])
        for invalid in ({'payload_days': 1}, {'summary_days': 6}, {'max_runs': 0}, {'max_runs': True}, {'unknown': 1}, {'auto_cleanup': 1}):
            (capped / 'storage.json').write_text(json.dumps(invalid))
            expect_value_error(lambda: dispatch({'operation': 'cleanup'}, capped))
        (capped / 'storage.json').unlink()

        safe = base / 'safe'
        db = setup(safe)
        rid, owned = run(db, safe, 22)
        outside = base / 'outside.txt'
        outside.write_text('must survive')
        unknown = owned.parent / 'unknown.txt'
        unknown.write_text('must survive')
        plan = json.loads(db.execute('SELECT plan FROM runs WHERE id=?', (rid,)).fetchone()[0])
        plan['records']['outside'] = str(outside)
        linked = owned.parent / 'linked.txt'
        symlink_supported = True
        try:
            linked.symlink_to(outside)
            plan['records']['linked'] = str(linked)
        except OSError:
            symlink_supported = False
        db.execute('UPDATE runs SET plan=? WHERE id=?', (json.dumps(plan), rid))
        db.commit()
        db.close()
        dispatch({'operation': 'cleanup', 'dry_run': False}, safe)
        assert outside.read_text() == 'must survive' and unknown.exists()
        if symlink_supported:
            assert linked.is_symlink()
        assert not owned.exists()

        atomic = base / 'atomic'
        db = setup(atomic)
        rid, owned = run(db, atomic, 33)
        db.execute("CREATE TRIGGER refuse_delete BEFORE DELETE ON runs BEGIN SELECT RAISE(ABORT,'refused'); END")
        db.commit()
        db.close()
        try:
            dispatch({'operation': 'cleanup', 'dry_run': False}, atomic)
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError('expected atomic abort')
        assert owned.exists()
        db = sqlite3.connect(atomic / 'runs.sqlite')
        assert db.execute('SELECT count(*) FROM runs').fetchone()[0] == 1
        assert db.execute('SELECT count(*) FROM run_summaries').fetchone()[0] == 0
        db.execute('DROP TRIGGER refuse_delete')
        db.commit()
        db.close()
        with patch.object(Path, 'unlink', side_effect=OSError('denied')):
            result = dispatch({'operation': 'cleanup', 'dry_run': False}, atomic)
        assert result['errors'] and owned.exists()
        db = sqlite3.connect(atomic / 'runs.sqlite')
        assert db.execute('SELECT count(*) FROM runs').fetchone()[0] == 0
        db.close()
        assert owned.exists()
        result = dispatch({'operation': 'cleanup', 'dry_run': False}, atomic)
        assert not owned.exists() and not result['archived_runs']
        db = sqlite3.connect(atomic / 'runs.sqlite')
        assert db.execute('SELECT count(*) FROM storage_pending_files').fetchone()[0] == 0
        db.close()

        # A label writer cannot commit while cleanup holds its protection snapshot.
        from crews.storage import _learning
        with _learning(root) as protected:
            assert {'labeled', 'family'} <= protected
            writer = sqlite3.connect(root / 'learning.sqlite', timeout=.1)
            try:
                writer.execute("INSERT INTO labels VALUES('new-label')")
                try:
                    writer.commit()
                except sqlite3.OperationalError as error:
                    assert error.sqlite_errorcode == sqlite3.SQLITE_BUSY
                else:
                    raise AssertionError('learning snapshot did not block label commit')
            finally:
                writer.rollback()
                writer.close()
        learning_lock = sqlite3.connect(root / 'learning.sqlite')
        learning_lock.execute('BEGIN EXCLUSIVE')
        before = snapshot(root)
        try:
            try:
                dispatch({'operation': 'cleanup'}, root)
            except sqlite3.OperationalError as error:
                assert error.sqlite_errorcode == sqlite3.SQLITE_BUSY
            else:
                raise AssertionError('readonly learning bypassed exclusive lock')
            assert snapshot(root) == before
        finally:
            learning_lock.rollback()
            learning_lock.close()

        compact = base / 'compact'
        db = setup(compact)
        db.execute('CREATE TABLE holes(payload BLOB)')
        db.executemany('INSERT INTO holes VALUES(?)', [(bytes(16384),)] * 128)
        db.commit()
        db.execute('DELETE FROM holes')
        db.commit()
        db.close()
        result = dispatch({'operation': 'compact'}, compact)
        assert result['reclaimed_bytes'] > 1_000_000
        assert result['after_bytes'] < result['before_bytes']
        lock = sqlite3.connect(compact / 'runs.sqlite')
        lock.execute('BEGIN IMMEDIATE')
        try:
            try:
                dispatch({'operation': 'compact'}, compact)
            except sqlite3.OperationalError as error:
                assert error.sqlite_errorcode in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
            else:
                raise AssertionError('expected busy compaction')
        finally:
            lock.rollback()
            lock.close()
        wal = sqlite3.connect(compact / 'runs.sqlite')
        wal.execute('PRAGMA journal_mode=WAL')
        wal.execute('INSERT INTO holes VALUES(?)', (b'live WAL',))
        wal.commit()
        before = snapshot(compact)
        expect_value_error(lambda: dispatch({'operation': 'status'}, compact))
        expect_value_error(lambda: dispatch({'operation': 'cleanup'}, compact))
        assert snapshot(compact) == before
        wal.close()
    print('storage checks passed')


if __name__ == '__main__':
    check()
