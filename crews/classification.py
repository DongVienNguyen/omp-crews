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
    behavior_fixed: StrictBool | None = None
    scope_bounded: StrictBool | None = None
    deterministic_check: StrictBool | None = None
    cross_system: StrictBool | None = None
    concurrency_sensitive: StrictBool | None = None


RUBRIC = {
    'version': 1,
    'precedence': 'valid declared answers; deterministic facts; semantic recommendation; require classification',
    'missing_facts': 'unknown, never false',
    'rules': {
        'bounded_guard': 'produce everyday_implementation difficulty <=1.5; explicit 1-3 files; true targets_fixed/behavior_fixed/scope_bounded/deterministic_check; false behavior_undecided/unknown_cause/consequential_judgment/cross_system/concurrency_sensitive; existing independent checker outside every writer scope and exact admitted command; missing facts unknown, retain Medium; never relabel repeatable_task',
        'unknown_cause': ['difficult_review', 3],
        'consequential_judgment': ['difficult_review', 3],
        'behavior_undecided': ['everyday_implementation', 1.5],
        'integration_behavior_undecided': ['integration_architecture', 2],
        'fixed_check': ['mechanical_verification', 0],
        'fixed_edit': ['repeatable_task', 0],
        'bounded_implementation': ['everyday_implementation', 1],
        'information_lookup': ['bounded_retrieval', 1],
    },
}


def policy_version():
    # Hash policy-owning code too: remaps and difficulty boundaries are not all catalog data.
    from pathlib import Path
    root = Path(__file__).resolve().parent
    sources = ['classification.py', 'omp_adapter.py', 'planner.py', 'budget.py', 'learning.py', 'outcomes.py', 'recipes.py', 'shaping.py', 'approval.py', 'accounting.py', 'evaluation.py', 'runner.py', 'automation.py', 'governance.py', 'portable_rules.py']
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


def classify_role(role, project=None, roles=None):
    if role.get('kind') not in catalog.load()['kinds']:
        raise ValueError('kind: valid role kind required')
    if not isinstance(role.get('mission'), str) or not role['mission'].strip(): raise ValueError('mission: nonempty objective required')
    if role.get('solution_space') is not None and (not isinstance(role['solution_space'], str) or not role['solution_space'].strip()): raise ValueError('solution_space: nonempty string required')
    if 'classification' in role and type(role['classification']) is not bool: raise ValueError('classification: strict boolean required')
    refuse(answer_errors(role, require_complete=False));facts=ClassificationFacts.model_validate({} if role.get('facts') is None else role['facts']).model_dump();refuse(safety_errors(role));answers=dict(role['answers']);declared=answers.get('need') is not None and answers.get('difficulty') is not None;suggestion=None;reason='insufficient deterministic evidence; supply need/difficulty or enable semantic recommendation'
    if declared: reason='valid declared need/difficulty take precedence'
    elif facts['unknown_cause'] is True or facts['consequential_judgment'] is True: suggestion=RUBRIC['rules']['unknown_cause'];reason='unknown cause or consequential judgment requires hard reasoning'
    elif facts['behavior_undecided'] is True: suggestion=RUBRIC['rules']['integration_behavior_undecided' if role['kind']=='integrate' else 'behavior_undecided'];reason='behavior or component seams remain undecided'
    elif role['kind']=='produce':
        from crews.omp_adapter import small_routes
        candidate={**role,'answers':{**answers,'need':answers.get('need') or 'everyday_implementation','difficulty':answers.get('difficulty') if answers.get('difficulty') is not None else 1}}
        if small_routes(candidate,project,roles)['small_route']: suggestion=RUBRIC['rules']['bounded_implementation'];reason='fixed implementation with independent check'
        elif not any(facts[key] is not None for key in ('behavior_fixed','scope_bounded','deterministic_check','cross_system','concurrency_sensitive')) and facts['method_fixed'] is True and facts['targets_fixed'] is True and all(facts[key] is False for key in ('behavior_undecided','unknown_cause','consequential_judgment')): suggestion=RUBRIC['rules']['fixed_edit'];reason='fully prescribed edit with no unresolved behavior'
    elif all(facts[key] is False for key in ('behavior_undecided','unknown_cause','consequential_judgment')):
        if role['kind']=='research' and facts['information_only'] is True and facts['targets_fixed'] is True: suggestion=RUBRIC['rules']['information_lookup'];reason='bounded information-only lookup of fixed targets'
        elif facts['method_fixed'] is True and facts['targets_fixed'] is True:
            if role['kind']=='check' and facts['criterion_fixed'] is True: suggestion=RUBRIC['rules']['fixed_check'];reason='fixed method, targets and criterion; deterministic verification'
            elif role['kind'] in ('produce','integrate'): suggestion=RUBRIC['rules']['fixed_edit'];reason='fully prescribed edit with no unresolved behavior'
    if suggestion:
        for key,value in zip(('need','difficulty'),suggestion):
            if answers.get(key) is None: answers[key]=value
    from crews.omp_adapter import model_policy
    from crews.omp_adapter import policy as active_policy
    policy=model_policy();combo_model=policy['combos'];classifier_model=active_policy()['classifier_model'];complete=answers.get('need') is not None and answers.get('difficulty') is not None
    if not complete:return {'answers':None,'reason':reason,'outcome':'requires_classification','tier':None,'policy_version':policy_version(),'classifier_model':classifier_model,'model_policy':combo_model}
    effective={**role,'answers':answers};refuse(answer_errors(effective)+safety_errors(effective));from crews.omp_adapter import preview_seat;seat=preview_seat(effective,project,roles);tier={'Small':'small','Medium':'medium','Large':'large'}[seat['policy_combo']]
    warnings=[]
    if declared and answers['need'] in ('everyday_implementation','difficult_review','integration_architecture') and all(facts[key] is False for key in ('behavior_undecided','unknown_cause','consequential_judgment')):
        if role['kind']=='research' and facts['information_only'] is True and facts['targets_fixed'] is True:warnings.append('review_declared_need: facts describe bounded information retrieval')
        if role['kind']=='check' and facts['method_fixed'] is True and facts['targets_fixed'] is True and facts['criterion_fixed'] is True:warnings.append('review_declared_need: facts describe deterministic verification')
    return {'answers':answers,'reason':reason,'warnings':warnings,'outcome':'declared' if declared else 'deterministic','tier':tier,**seat,'policy_version':policy_version(),'classifier_model':classifier_model,'model_policy':combo_model}
