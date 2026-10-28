"""Local-account policy only: no signing, code, commands or credential authority."""
import getpass
import hashlib
import json
import math
import os
import socket
import uuid
from pathlib import Path

DEFAULTS = dict(lease_seconds=86400, max_reviews=100, max_difficulty=1,
                auto_promotion=dict(min_train=3, min_holdout=5, max_failure_bound=.05),
                mode='on', auto_evidence=True, routing={}, audit_every=10)


def account_binding(folder):
    # Local-account trust, not cryptographic approval or protection from same-user code.
    identity = [socket.gethostname(), getpass.getuser(), str(Path(folder).resolve()).casefold()]
    if hasattr(os, 'getuid'):
        identity.append(str(os.getuid()))
    return hashlib.sha256(json.dumps(identity).encode()).hexdigest()


def installation(folder):
    target = Path(folder) / 'automation-local.json'
    if not target.is_file():
        return None
    value = json.loads(target.read_text(encoding='utf-8'))
    if (not isinstance(value, dict) or set(value) != {'version', 'identity', 'account_binding', 'enabled'}
            or value['version'] != 1 or type(value['enabled']) is not bool
            or not isinstance(value['identity'], str) or len(value['identity']) != 32
            or value['account_binding'] != account_binding(folder)):
        raise ValueError('local automation installation belongs to another account or state location')
    try:
        uuid.UUID(hex=value['identity'])
    except ValueError as exc:
        raise ValueError('invalid local installation identity') from exc
    return value


def install(folder, enabled=None):
    if enabled is not None and type(enabled) is not bool:
        raise ValueError('enabled must be boolean')
    folder = Path(folder)
    value = installation(folder)
    if value is None:
        value = dict(version=1, identity=uuid.uuid4().hex,
                     account_binding=account_binding(folder), enabled=True)
    if enabled is not None:
        value['enabled'] = enabled
    folder.mkdir(parents=True, exist_ok=True)
    temporary = folder / ('automation-local.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps(value, sort_keys=True) + '\n', encoding='utf-8')
        os.replace(temporary, folder / 'automation-local.json')
    finally:
        temporary.unlink(missing_ok=True)
    return value


def validate(value):
    from crews import catalog, recipes
    if not isinstance(value, dict) or set(value) != set(DEFAULTS):
        raise ValueError('policy requires exactly ' + ', '.join(DEFAULTS))
    for name, low, high in [('lease_seconds', 1, 90 * 86400), ('max_reviews', 1, 1000), ('audit_every', 1, 1000)]:
        if type(value[name]) is not int or not low <= value[name] <= high:
            raise ValueError(name + ' must be integer ' + str(low) + '..' + str(high))
    difficulty = value['max_difficulty']
    if isinstance(difficulty, bool) or not isinstance(difficulty, (int, float)) or not math.isfinite(difficulty) or not 0 <= difficulty <= 1:
        raise ValueError('supported max_difficulty ceiling is 1 (routine implementation)')
    if value['mode'] not in ('off', 'shadow', 'on') or type(value['auto_evidence']) is not bool:
        raise ValueError('mode off/shadow/on and boolean auto_evidence required')
    policy = recipes._policy(value['auto_promotion'])
    if policy is not None and not math.isfinite(policy['max_failure_bound']):
        raise ValueError('auto_promotion bound must be finite')
    routing = value['routing']
    if not isinstance(routing, dict) or set(routing) - set(catalog.load()['needs']) or any(not isinstance(v, str) or v not in ('Small', 'Medium', 'Large') for v in routing.values()):
        raise ValueError('routing requires supported need -> Small/Medium/Large map')
    # Hard independent checking and consequential review never downgrade through policy.
    if any(routing.get(need, 'Large') != 'Large' for need in ('difficult_review', 'integration_architecture')):
        raise ValueError('difficult_review/integration_architecture must retain Large')
    return json.loads(json.dumps(value, allow_nan=False))


def schema():
    from crews import catalog
    promotion = dict(type='object', additionalProperties=False,
                     required=['min_train', 'min_holdout', 'max_failure_bound'],
                     properties=dict(min_train=dict(type='integer', minimum=3),
                                     min_holdout=dict(type='integer', minimum=5),
                                     max_failure_bound=dict(type='number', exclusiveMinimum=0, maximum=.05)))
    properties = dict(lease_seconds=dict(type='integer', minimum=1, maximum=90 * 86400),
                      max_reviews=dict(type='integer', minimum=1, maximum=1000),
                      max_difficulty=dict(type='number', minimum=0, maximum=1),
                      auto_promotion=dict(anyOf=[promotion, dict(type='null')]),
                      mode=dict(enum=['off', 'shadow', 'on']), auto_evidence=dict(type='boolean'),
                      audit_every=dict(type='integer', minimum=1, maximum=1000),
                      routing=dict(type='object', additionalProperties=False, properties={
                          need: dict(enum=['Large'] if need in ('difficult_review', 'integration_architecture') else ['Small', 'Medium', 'Large'])
                          for need in catalog.load()['needs']}))
    policy = dict(type='object', additionalProperties=False, required=list(DEFAULTS), properties=properties)
    return dict(type='object', additionalProperties=False, required=['decision', 'policy', 'reason'],
                properties=dict(decision=dict(enum=['approve', 'deny']),
                                policy=dict(anyOf=[policy, dict(type='null')]),
                                reason=dict(type='string', minLength=1)),
                description='Crews policy only. Supported routine max_difficulty <=1; promotion >=3 train, >=5 holdout, bound <=.05. No code, command, model or credential authority.')


def decision(value):
    if (not isinstance(value, dict) or set(value) != {'decision', 'policy', 'reason'}
            or not isinstance(value['reason'], str) or not value['reason'].strip()):
        raise ValueError('typed Large policy_decision required')
    if value['decision'] == 'deny' and value['policy'] is None:
        raise ValueError('Large denied governance: ' + value['reason'])
    if value['decision'] != 'approve':
        raise ValueError('Large governance decision denied or malformed')
    return validate(value['policy'])
