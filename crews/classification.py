"""Pure classification: facts are evidence, never execution authority."""
import hashlib
import json
import math
from pydantic import BaseModel, ConfigDict, StrictBool
from crews import catalog


class ClassificationFacts(BaseModel):
    model_config = ConfigDict(extra='forbid')
    method_fixed: StrictBool | None = None
    targets_fixed: StrictBool | None = None
    behavior_undecided: StrictBool | None = None
    unknown_cause: StrictBool | None = None
    consequential_judgment: StrictBool | None = None
    information_only: StrictBool | None = None
    criterion_fixed: StrictBool | None = None


RUBRIC = {
    'version': 1,
    'precedence': 'valid declared answers; deterministic facts; semantic recommendation; require classification',
    'missing_facts': 'unknown, never false',
    'rules': {
        'unknown_cause': ['difficult_review', 3],
        'consequential_judgment': ['difficult_review', 3],
        'behavior_undecided': ['everyday_implementation', 1.5],
        'integration_behavior_undecided': ['integration_architecture', 2],
        'fixed_check': ['mechanical_verification', 0],
        'fixed_edit': ['repeatable_task', 0],
        'information_lookup': ['bounded_retrieval', 1],
    },
}


def policy_version():
    # Hash policy-owning code too: remaps and difficulty boundaries are not all catalog data.
    from pathlib import Path
    root = Path(__file__).resolve().parent
    sources = ['classification.py', 'omp_adapter.py', 'planner.py', 'budget.py']
    from crews.omp_adapter import model_policy
    payload = {'catalog': catalog.load(), 'rubric': RUBRIC, 'model_policy':model_policy(),
               'sources': {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in sources}}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def answer_errors(role, require_complete=True):
    errors = []
    answers = role.get('answers')
    if not isinstance(answers, dict):
        return [(('answers',), 'flat role answers object required')]
    allowed = {'need', 'difficulty', 'divisible', 'specific'}
    errors += [(('answers', key), 'unknown answer field') for key in answers.keys() - allowed]
    need = answers.get('need')
    if (require_complete or need is not None) and need not in catalog.load()['needs']:
        errors.append((('answers', 'need'), 'valid need required'))
    for key, maximum in [('difficulty', 3), ('divisible', 1), ('specific', 1)]:
        value = answers.get(key)
        required = key == 'divisible' or (key == 'specific' and role.get('classification') is True) or (key == 'difficulty' and require_complete)
        if value is None and not required:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= maximum:
            errors.append((('answers', key), f'number from 0 to {maximum} required'))
    return errors


def safety_errors(role):
    """No text inference: untrusted objectives cannot override declared evidence."""
    facts = ClassificationFacts.model_validate({} if role.get('facts') is None else role['facts']).model_dump()
    need = (role.get('answers') or {}).get('need')
    difficulty = (role.get('answers') or {}).get('difficulty')
    errors = []
    cheap = {'bounded_retrieval', 'repeatable_task', 'mechanical_verification'}
    for key in ('unknown_cause', 'consequential_judgment'):
        if facts[key] is True:
            if need is not None and need != 'difficult_review':
                errors.append((('answers', 'need'), f'contradicts facts.{key}=true; requires difficult_review'))
            if difficulty is not None and difficulty < 2.5:
                errors.append((('answers', 'difficulty'), f'contradicts facts.{key}=true; requires difficulty >= 2.5'))
    if facts['behavior_undecided'] is True and need in cheap:
        errors.append((('answers', 'need'), 'contradicts facts.behavior_undecided=true'))
    if facts['information_only'] is True and role.get('kind') in ('produce', 'integrate'):
        errors.append((('facts', 'information_only'), 'information-only role cannot grant writing kind'))
    if role.get('facts'):
        if need == 'mechanical_verification' and role.get('kind') != 'check':
            errors.append((('answers', 'need'), 'mechanical_verification with facts requires check kind'))
        if need == 'repeatable_task' and role.get('kind') not in ('produce', 'integrate'):
            errors.append((('answers', 'need'), 'repeatable_task with facts requires produce or integrate kind'))
    return errors


def refuse(errors):
    if errors:
        raise ValueError('; '.join('.'.join(map(str, loc)) + ': ' + message for loc, message in errors))


def classify_role(role):
    """No state, providers, scope expansion, or keyword-based cheap defaults."""
    if role.get('kind') not in catalog.load()['kinds']:
        raise ValueError('kind: valid role kind required')
    if not isinstance(role.get('mission'), str) or not role['mission'].strip():
        raise ValueError('mission: nonempty objective required')
    solution_space = role.get('solution_space')
    if solution_space is not None and (not isinstance(solution_space, str) or not solution_space.strip()):
        raise ValueError('solution_space: nonempty string required')
    if 'classification' in role and type(role['classification']) is not bool:
        raise ValueError('classification: strict boolean required')
    refuse(answer_errors(role, require_complete=False))
    facts = ClassificationFacts.model_validate({} if role.get('facts') is None else role['facts']).model_dump()
    refuse(safety_errors(role))
    answers = dict(role['answers'])
    declared = answers.get('need') is not None and answers.get('difficulty') is not None
    suggestion = None
    reason = 'insufficient deterministic evidence; supply need/difficulty or enable semantic recommendation'
    if declared:
        reason = 'valid declared need/difficulty take precedence'
    elif facts['unknown_cause'] is True or facts['consequential_judgment'] is True:
        suggestion = RUBRIC['rules']['unknown_cause']
        reason = 'unknown cause or consequential judgment requires hard reasoning'
    elif facts['behavior_undecided'] is True:
        suggestion = RUBRIC['rules']['integration_behavior_undecided' if role['kind'] == 'integrate' else 'behavior_undecided']
        reason = 'behavior or component seams remain undecided'
    elif all(facts[key] is False for key in ('behavior_undecided', 'unknown_cause', 'consequential_judgment')):
        if role['kind'] == 'research' and facts['information_only'] is True and facts['targets_fixed'] is True:
            suggestion = RUBRIC['rules']['information_lookup']
            reason = 'bounded information-only lookup of fixed targets'
        elif facts['method_fixed'] is True and facts['targets_fixed'] is True:
            if role['kind'] == 'check' and facts['criterion_fixed'] is True:
                suggestion = RUBRIC['rules']['fixed_check']
                reason = 'fixed method, targets and criterion; deterministic verification'
            elif role['kind'] in ('produce', 'integrate'):
                suggestion = RUBRIC['rules']['fixed_edit']
                reason = 'fully prescribed edit with no unresolved behavior or judgment'
    if suggestion:
        for key, value in zip(('need', 'difficulty'), suggestion):
            if answers.get(key) is None:
                answers[key] = value
    complete = answers.get('need') is not None and answers.get('difficulty') is not None
    if complete:
        effective = {**role, 'answers': answers}
        refuse(answer_errors(effective) + safety_errors(effective))
        from crews.omp_adapter import preview_seat
        seat = preview_seat(effective)
        tier = {'code-seek': 'mechanical', 'code-sol': 'implementation', 'code-astra': 'reasoning'}[seat['policy_model']]
    else:
        answers, tier = None, None
    from crews.omp_adapter import model_policy
    policy=model_policy()
    return {'answers': answers, 'reason': reason,
            'outcome': 'declared' if declared else 'deterministic' if complete else 'requires_classification',
            'tier': tier, 'policy_version': policy_version(),
            'classifier_model':policy['provider']+'/'+policy['models']['haiku']+':high'}
