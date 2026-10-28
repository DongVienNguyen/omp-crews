"""Explicit local retention. Summaries are history only, never dispatchable plans."""
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import stat
import time
from contextlib import closing, contextmanager, ExitStack

DAY = 86400
DEFAULTS = {'payload_days': 7, 'summary_days': 90, 'max_runs': 1000, 'auto_cleanup': True}
TABLES = ('runs', 'calls', 'attempts', 'tickets', 'admissions', 'receipts', 'run_summaries')
HEX = re.compile(r'[0-9a-f]{32}\Z')
SUMMARY_SCHEMA = ('CREATE TABLE IF NOT EXISTS run_summaries '
                  '(run TEXT PRIMARY KEY, project TEXT, session TEXT, created REAL, summary TEXT)')
PENDING_SCHEMA = 'CREATE TABLE IF NOT EXISTS storage_pending_files(path TEXT PRIMARY KEY)'


def _root(state):
    return Path(state or os.environ.get('CREWS_OMP_HOME', str(Path.home() / '.crews-omp'))).absolute()


def _regular(path, root):
    """Never follow links, junctions, or paths outside the owned state tree."""
    try:
        relative = path.relative_to(root)
        parts = [root, *(root.joinpath(*relative.parts[:i]) for i in range(1, len(relative.parts) + 1))]
        for part in parts:
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                return False
        return stat.S_ISREG(path.lstat().st_mode)
    except (OSError, ValueError):
        return False


def _retention(root):
    target = root / 'storage.json'
    if not target.exists() and not target.is_symlink():
        return dict(DEFAULTS)
    if not _regular(target, root):
        raise ValueError('storage: invalid retention')
    try:
        value = json.loads(target.read_text(encoding='utf-8'))
    except (ValueError, OSError):
        raise ValueError('storage: invalid retention') from None
    if not isinstance(value, dict) or set(value) - set(DEFAULTS):
        raise ValueError('storage: invalid retention')
    value = {**DEFAULTS, **value}
    if (any(type(value[k]) is not int for k in ('payload_days', 'summary_days', 'max_runs'))
            or type(value['auto_cleanup']) is not bool or value['payload_days'] < 2
            or value['summary_days'] < value['payload_days'] or value['max_runs'] < 1):
        raise ValueError('storage: invalid retention')
    return value


def _connect(root, readonly=True, filename='runs.sqlite'):
    target = root / filename
    if not _regular(target, root):
        raise ValueError('storage: unsafe state')
    # Immutable readers never create/change WAL sidecars. A nonempty WAL needs a
    # live SQLite reader, so readonly operations refuse until writers finish.
    wal = root / (filename + '-wal')
    uri = target.as_uri() + '?mode=ro&immutable=1' if readonly else target.as_uri() + '?mode=rw'
    if readonly and (wal.exists() or wal.is_symlink()):
        if not _regular(wal, root) or wal.stat().st_size:
            raise ValueError('storage: busy; retry after active work finishes')
    db = sqlite3.connect(uri, uri=True, timeout=1, isolation_level=None)
    db.row_factory = sqlite3.Row
    return db


def _tables(db):
    return {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _rows(db, tables, table):
    return list(db.execute('SELECT * FROM ' + table)) if table in tables else []


def _json(raw):
    try:
        value = json.loads(raw or '{}')
    except (ValueError, TypeError):
        raise ValueError('storage: unsafe state') from None
    if not isinstance(value, dict):
        raise ValueError('storage: unsafe state')
    return value


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _legacy(root, now, errors):
    live, expired, tokens = {}, [], set()
    folder = root / 'tickets'
    if not folder.exists() and not folder.is_symlink():
        return live, expired, tokens
    if folder.is_symlink() or not folder.is_dir() or folder.resolve() != folder:
        raise ValueError('storage: unsafe state')
    for path in sorted(folder.iterdir()):
        token = path.stem
        if path.suffix != '.json' or not HEX.fullmatch(token) or not _regular(path, root):
            errors.append({'path': str(path.relative_to(root)), 'error': 'unsafe or unknown file'})
            if HEX.fullmatch(token):
                tokens.add(token)
            continue
        try:
            item = _json(path.read_text(encoding='utf-8'))
            if (item.get('token') != token or not HEX.fullmatch(str(item.get('run', '')))
                    or not _number(item.get('expires'))):
                raise ValueError('storage: unsafe state')
        except (ValueError, OSError):
            tokens.add(token)
            errors.append({'path': str(path.relative_to(root)), 'error': 'invalid ticket'})
            continue
        if item['expires'] >= now:
            live[item['run']] = 'live legacy ticket'
            tokens.add(token)
        elif item['expires'] < now - 3600:
            expired.append((path, token))
    return live, expired, tokens


@contextmanager
def _learning(root):
    path = root / 'learning.sqlite'
    if not path.exists() and not path.is_symlink():
        yield set()
        return
    if not _regular(path, root):
        raise ValueError('storage: unsafe state')
    # Real readonly rollback-journal readers honor locks and stop labels/rules
    # committing between protection selection and the archive transaction commit.
    # Refuse WAL before opening it: readonly WAL readers may still change shm.
    with path.open('rb') as source:
        header = source.read(20)
    if len(header) < 20 or header[18:20] != b'\x01\x01':
        raise ValueError('storage: busy; retry after active work finishes')
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=1,
                                 isolation_level=None)) as db:
        db.execute('BEGIN')
        try:
            tables=_tables(db)
            protected=set()
            if {'labels','observations','rules'}<=tables:
                protected={row[0] for row in db.execute('''
                    SELECT observation_id FROM labels
                    UNION SELECT o.id FROM observations o JOIN rules r
                    ON r.project=o.project AND r.signature=o.signature AND r.policy=o.policy
                    WHERE r.state IN ('candidate','shadow_ready','active')
                ''')}
            if 'recipe_v1_evidence' in tables:
                for row in db.execute('SELECT proof FROM recipe_v1_evidence'):
                    proof=_json(row[0])
                    if proof.get('run'):protected.add('recipe-run:'+str(proof['run']))
            if 'recipe_v1_captures' in tables:
                protected.update('recipe-run:'+str(row[0]) for row in db.execute('SELECT run FROM recipe_v1_captures'))
            if 'automation_jobs' in tables:
                for row in db.execute('SELECT run,request FROM automation_jobs'):
                    if row[0]:protected.add('recipe-run:'+str(row[0]))
                    request=_json(row[1]);source=request.get('source',request)
                    if source.get('run'):protected.add('recipe-run:'+str(source['run']))
            yield protected
        finally:
            db.rollback()


def _cells(plan):
    return [cell for wave in plan.get('waves', []) for cell in wave.get('calls', [])]


def _summary(plan, calls, attempts):
    output = []
    by_role = {r['role']: r for r in calls}
    counters = {r['role']: r for r in attempts}
    for cell in _cells(plan):
        role = cell.get('role_id')
        call = by_role.get(role)
        result = _json(call['result']) if call and call['result'] else {}
        native = result.get('native') or {}
        usage = native.get('usage') or {}
        item = {'role_id': role, 'combo': cell.get('policy_combo'), 'model': cell.get('model'),
                'effort': cell.get('reasoning_effort'), 'status': call['status'] if call else None,
                'usage': {k: v for k, v in usage.items() if k in
                          {'input', 'output', 'inputTokens', 'outputTokens', 'cacheRead', 'cacheWrite',
                           'totalTokens', 'total', 'cost'} and _number(v)}}
        for key in ('requested_combo', 'effective_combo', 'bounded_small', 'small_route', 'small_blockers', 'routing_reason', 'routing_policy_version'):
            if key in cell:
                item[key] = cell[key]
        if result.get('outcome'):
            item['outcome'] = result['outcome']
        item['native_model_known'] = bool(native.get('resolvedModel'))
        if _number(native.get('durationMs')):
            item['duration_ms'] = native['durationMs']
        counter = counters.get(role)
        item['attempts'] = {key: counter[key] if counter else 0 for key in ('escalations', 'repairs')}
        output.append(item)
    return {'roles': output, 'attempts': {key: sum(r['attempts'][key] for r in output)
                                        for key in ('escalations', 'repairs')}}


def _record_paths(root, run, plan, errors):
    if not HEX.fullmatch(run):
        return []
    base = root / 'records' / run
    result = []
    records = plan.get('records') or {}
    if not isinstance(records, dict):
        raise ValueError('storage: unsafe state')
    for raw in records.values():
        if not isinstance(raw, str):
            continue
        path = Path(raw)
        if not path.is_absolute():
            # Owned records are emitted with an absolute record root by the planner.
            continue
        try:
            rel = path.relative_to(base)
        except ValueError:
            continue
        if '..' in rel.parts or not rel.parts or rel.parts[0] != 'roles':
            continue
        if _regular(path, root):
            result.append(path)
        elif path.exists() or path.is_symlink():
            errors.append({'path': str(path.relative_to(root)), 'error': 'unsafe record file'})
    return result


def _plan(root, db, retention, now, learning=None):
    if learning is None:
        with _learning(root) as protected:
            return _plan(root, db, retention, now, protected)
    tables = _tables(db) if db else set()
    runs = _rows(db, tables, 'runs') if db else []
    calls = _rows(db, tables, 'calls') if db else []
    attempts = _rows(db, tables, 'attempts') if db else []
    admissions = _rows(db, tables, 'admissions') if db else []
    tickets = _rows(db, tables, 'tickets') if db else []
    summaries = _rows(db, tables, 'run_summaries') if db else []
    errors = []
    protected, expired, live_tokens = _legacy(root, now, errors)
    for item in admissions:
        if not _number(item['expires']):
            raise ValueError('storage: unsafe state')
        if item['expires'] >= now:
            protected[item['run']] = 'live admission'
            live_tokens.add(item['token'])
    for item in tickets:
        if item['token'] in live_tokens:
            protected[item['run']] = 'live ticket token'
    archived, files = [], []
    plans = {}
    for row in runs:
        run = row['id']
        if not _number(row['created']):
            raise ValueError('storage: unsafe state')
        plan = _json(row['plan'])
        plans[run] = plan
        if row['created'] >= now - DAY:
            protected[run] = 'fresh run'
        if any(cell.get('classification', {}).get('learning', {}).get('observation_id') in learning
               for cell in _cells(plan)):
            protected[run] = 'learning reference'
        if 'recipe-run:'+run in learning:protected[run]='verified recipe evidence'
        if run not in protected:
            if row['created'] < now - retention['payload_days'] * DAY:
                archived.append(row)
            # Record files have their own expiry, independent of retained SQLite evidence.
            if row['created'] < now - 2 * DAY:
                files.extend(path for path in _record_paths(root, run, plan, errors)
                             if path.stat().st_mtime < now - DAY)
    expired_tokens = {token for _, token in expired}
    # Database admissions carry authoritative expiry for wire files after cutover.
    expired_tokens.update(r['token'] for r in admissions if r['expires'] < now - 3600)
    for path, token in expired:
        if token not in live_tokens:
            files.append(path)
    wire = root / 'wire'
    if wire.is_symlink() or (wire.exists() and (not wire.is_dir() or wire.resolve() != wire)):
        raise ValueError('storage: unsafe state')
    if wire.is_dir():
        for path in sorted(wire.iterdir()):
            if path.suffix == '.json' and HEX.fullmatch(path.stem) and path.stem in expired_tokens and path.stem not in live_tokens and _regular(path, root):
                files.append(path)
            elif path.stem not in live_tokens:
                errors.append({'path': str(path.relative_to(root)), 'error': 'unsafe or unknown file'})
    all_summaries = {r['run']: r['created'] for r in summaries}
    all_summaries.update({r['id']: r['created'] for r in archived})
    keep = sorted(((run, created) for run, created in all_summaries.items()
                   if created >= now - retention['summary_days'] * DAY), key=lambda r: (r[1], r[0]), reverse=True)
    kept = {run for run, _ in keep[:retention['max_runs']]}
    trim = sorted(set(all_summaries) - kept)
    return {'tables': tables, 'archived': archived, 'plans': plans, 'calls': calls, 'attempts': attempts,
            'files': sorted(set(files)), 'protected': protected, 'trim': trim, 'errors': errors,
            'live_tokens': live_tokens, 'admissions': admissions, 'tickets': tickets,
            'expired_tokens': sorted(expired_tokens - live_tokens)}


def _pending_path(root, raw, plan):
    relative = Path(raw)
    parts = relative.parts
    if relative.is_absolute() or '..' in parts or not parts:
        return None
    if parts[0] == 'records':
        if len(parts) < 5 or not HEX.fullmatch(parts[1]) or parts[2] != 'roles':
            return None
        if parts[1] in plan['protected']:
            return None
    elif parts[0] in ('tickets', 'wire'):
        if len(parts) != 2 or relative.suffix != '.json' or not HEX.fullmatch(relative.stem):
            return None
        if relative.stem in plan['live_tokens']:
            return None
        ticket = root / 'tickets' / relative.name
        if ticket.exists() or ticket.is_symlink():
            if not _regular(ticket, root):
                return None
            try:
                value = _json(ticket.read_text(encoding='utf-8'))
                if not _number(value.get('expires')) or value['expires'] >= time.time() - 3600:
                    return None
            except (OSError, ValueError):
                return None
    else:
        return None
    path = root / relative
    for part in (path, *path.parents):
        if part == root:
            break
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            return None
    return path


def _file_stats(root):
    areas = {}
    if root.exists() and not root.is_symlink():
        for folder, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = [d for d in dirs if not (Path(folder) / d).is_symlink()
                       and not getattr((Path(folder) / d).lstat(), 'st_file_attributes', 0) & 0x400]
            for name in files:
                path = Path(folder) / name
                if _regular(path, root):
                    relative = path.relative_to(root)
                    area = relative.parts[0] if len(relative.parts) > 1 else 'root'
                    item = areas.setdefault(area, {'count': 0, 'bytes': 0})
                    item['count'] += 1
                    item['bytes'] += path.stat().st_size
    return {'count': sum(r['count'] for r in areas.values()), 'bytes': sum(r['bytes'] for r in areas.values()), 'by_area': areas}


def _db_bytes(root):
    return sum(path.stat().st_size for path in (root / 'runs.sqlite', root / 'runs.sqlite-wal') if _regular(path, root))


def _status(root, retention):
    result = {'operation': 'status', 'state': str(root), 'retention': retention, 'files': _file_stats(root),
              'database': {'exists': False, 'bytes': 0, 'page_count': 0, 'freelist_count': 0, 'page_size': 0,
                           'counts': {key: 0 for key in TABLES}}}
    target = root / 'runs.sqlite'
    if target.exists() or target.is_symlink():
        with closing(_connect(root)) as db:
            tables = _tables(db)
            result['database'].update({'exists': True, 'bytes': _db_bytes(root),
                                      **{key: db.execute('PRAGMA ' + key).fetchone()[0]
                                         for key in ('page_count', 'freelist_count', 'page_size')},
                                      'counts': {key: db.execute('SELECT count(*) FROM ' + key).fetchone()[0] if key in tables else 0 for key in TABLES}})
            protection = _plan(root, db, retention, time.time())['protected']
            result['protected_runs'] = protection
            result['protected_count'] = len(protection)
    return result


def _cleanup(root, retention, dry_run):
    target = root / 'runs.sqlite'
    db = _connect(root, readonly=dry_run) if target.exists() or target.is_symlink() else None
    learning = ExitStack()
    try:
        protected = learning.enter_context(_learning(root))
        if db and not dry_run:
            db.execute('BEGIN IMMEDIATE')
        # Compute under the write lock, never apply a stale dry-run plan.
        plan = _plan(root, db, retention, time.time(), protected)
        if db and 'storage_pending_files' in plan['tables']:
            for row in db.execute('SELECT path FROM storage_pending_files'):
                path = _pending_path(root, row['path'], plan)
                if path is not None:
                    plan['files'].append(path)
                else:
                    plan['errors'].append({'path': row['path'], 'error': 'unsafe or protected pending file'})
            plan['files'] = sorted(set(plan['files']))
        result = {'operation': 'cleanup', 'dry_run': dry_run, 'retention': retention,
                  'archived_runs': [r['id'] for r in plan['archived']], 'trimmed_summaries': plan['trim'],
                  'deleted_files': [str(p.relative_to(root)) for p in plan['files']],
                  'protected_runs': plan['protected'], 'errors': plan['errors'],
                  'expired_tokens': plan['expired_tokens']}
        if dry_run:
            return result
        if db:
            db.execute(SUMMARY_SCHEMA)
            db.execute(PENDING_SCHEMA)
            db.executemany('INSERT OR IGNORE INTO storage_pending_files VALUES(?)',
                           [(str(path.relative_to(root)),) for path in plan['files']])
            for row in plan['archived']:
                run = row['id']
                summary = _summary(plan['plans'][run], [r for r in plan['calls'] if r['run'] == run],
                                   [r for r in plan['attempts'] if r['run'] == run])
                db.execute('INSERT OR REPLACE INTO run_summaries VALUES(?,?,?,?,?)',
                           (run, row['project'], row['session'], row['created'], json.dumps(summary, separators=(',', ':'))))
                tokens = {r['token'] for r in [*plan['admissions'], *plan['tickets']] if r['run'] == run}
                if 'receipts' in plan['tables']:
                    for receipt in db.execute('SELECT token,payload FROM receipts').fetchall():
                        if receipt['token'] in tokens or _json(receipt['payload']).get('run') == run:
                            db.execute('DELETE FROM receipts WHERE token=?', (receipt['token'],))
                for token in tokens:
                    for table in ('tool_receipts','profile_receipts'):
                        if table in plan['tables']:db.execute('DELETE FROM '+table+' WHERE token=?',(token,))
                for table in ('dispatch_secrets','run_accounting'):
                    if table in plan['tables']:db.execute('DELETE FROM '+table+' WHERE run=?',(run,))
                for table in ('calls', 'attempts', 'tickets', 'admissions'):
                    if table in plan['tables']:
                        db.execute('DELETE FROM ' + table + ' WHERE run=?', (run,))
                db.execute('DELETE FROM runs WHERE id=?', (run,))
            db.executemany('DELETE FROM run_summaries WHERE run=?', [(run,) for run in plan['trim']])
            for token in plan['expired_tokens']:
                for table in ('receipts', 'admissions', 'tickets'):
                    if table in plan['tables']:
                        db.execute('DELETE FROM ' + table + ' WHERE token=?', (token,))
            db.commit()
        if db:
            db.execute('BEGIN IMMEDIATE')
        # Filesystem failures cannot undo committed SQL; report every failure explicitly.
        deleted = []
        for path in plan['files']:
            relative = str(path.relative_to(root))
            try:
                if db and path.parent.name in ('tickets', 'wire') and 'admissions' in plan['tables']:
                    if db.execute('SELECT 1 FROM admissions WHERE token=? AND expires>=?',
                                  (path.stem, time.time())).fetchone():
                        raise OSError('live admission')
                if path.exists() or path.is_symlink():
                    if _pending_path(root, relative, plan) is None or not _regular(path, root):
                        raise OSError('unsafe file')
                    path.unlink()
                    deleted.append(relative)
                if db:
                    db.execute('DELETE FROM storage_pending_files WHERE path=?', (relative,))
                if path.is_relative_to(root / 'records'):
                    for folder in path.parents:
                        if folder == root / 'records':
                            break
                        if folder.is_symlink() or folder.resolve() != folder:
                            break
                        try:
                            folder.rmdir()
                        except OSError:
                            break
            except OSError:
                result['errors'].append({'path': relative, 'error': 'unlink failed or unsafe file'})
        if db:
            db.commit()
        result['deleted_files'] = deleted
        return result
    except BaseException:
        if db and db.in_transaction:
            db.rollback()
        raise
    finally:
        learning.close()
        if db:
            db.close()


def _compact(root):
    target = root / 'runs.sqlite'
    if not target.exists() and not target.is_symlink():
        return {'operation': 'compact', 'before_bytes': 0, 'after_bytes': 0, 'reclaimed_bytes': 0,
                'checkpoint': {'busy': 0, 'log': 0, 'checkpointed': 0}}
    with closing(_connect(root, readonly=False)) as db:
        # Retain the exclusive database lock across checkpoint and VACUUM, which
        # cannot run inside a transaction; no admission can race the safety check.
        db.execute('PRAGMA locking_mode=EXCLUSIVE')
        db.execute('BEGIN IMMEDIATE')
        try:
            now = time.time()
            tables = _tables(db)
            live, _, tokens = _legacy(root, now, [])
            admitted = ('calls' in tables and 'runs' in tables and db.execute(
                "SELECT 1 FROM calls c JOIN runs r ON r.id=c.run WHERE c.status='admitted' AND r.created>=? LIMIT 1", (now - DAY,)).fetchone())
            active = ('admissions' in tables and db.execute('SELECT 1 FROM admissions WHERE expires>=? LIMIT 1', (now,)).fetchone())
            if admitted or active or live or tokens:
                raise ValueError('storage: compact refused while work is active')
            db.commit()
        except BaseException:
            db.rollback()
            raise
        before = _db_bytes(root)
        checkpoint = db.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()
        if checkpoint[0]:
            raise ValueError('storage: checkpoint busy')
        db.execute('VACUUM')
        final_checkpoint = db.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()
        if final_checkpoint[0]:
            raise ValueError('storage: checkpoint busy')
        after = _db_bytes(root)
        return {'operation': 'compact', 'before_bytes': before, 'after_bytes': after,
                'reclaimed_bytes': max(0, before - after),
                'checkpoint': dict(zip(('busy', 'log', 'checkpointed'), checkpoint))}


def dispatch(request, state=None):
    if (not isinstance(request, dict) or set(request) - {'operation', 'dry_run'}
            or request.get('operation') not in ('status', 'cleanup', 'compact')
            or ('dry_run' in request and (request['operation'] != 'cleanup' or type(request['dry_run']) is not bool))):
        raise ValueError('storage: invalid request')
    root = _root(state)
    if root.is_symlink() or (root.exists() and (not root.is_dir() or root.resolve() != root)):
        raise ValueError('storage: unsafe state')
    retention = _retention(root)
    operation = request['operation']
    if operation == 'status':
        return _status(root, retention)
    if operation == 'cleanup':
        return _cleanup(root, retention, request.get('dry_run', True))
    return _compact(root)
