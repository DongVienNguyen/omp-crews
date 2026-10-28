"""SDLC routing contracts: 27 matrix rows and behavior counterexamples; no provider or state writes."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch
import uuid

from pydantic import ValidationError
from crews import omp_adapter as adapter
from crews.classification import HOST_FIELDS, RiskFacts, RoleMetadata, Stage
from omp_server import IntakeRoleSpec, PlanSpec, RoleSpec


FIXED = {'method_fixed': True, 'targets_fixed': True, 'behavior_undecided': False,
         'unknown_cause': False, 'consequential_judgment': False}
LOOKUP = {**FIXED, 'information_only': True}
CHECK = {**FIXED, 'criterion_fixed': True}
WRITER = {'targets_fixed': True, 'method_fixed': False, 'behavior_undecided': True,
          'unknown_cause': False, 'consequential_judgment': False}


def role(kind, mission, need=None, difficulty=None, facts=None, **extra):
    answers = {'divisible': 0, 'specific': 1}
    if need is not None:
        answers['need'] = need
    if difficulty is not None:
        answers['difficulty'] = difficulty
    return {'name': 'sdlc-case', 'kind': kind, 'mission': mission, 'deliverable': 'result.json',
            'classification': True, 'answers': answers,
            **({'facts': deepcopy(facts)} if facts is not None else {}), **extra}


def expect(candidate, need, combo):
    before = deepcopy(candidate)
    IntakeRoleSpec.model_validate(candidate)
    result = adapter.preview(candidate)
    assert candidate == before, 'classification mutated caller'
    assert result['answers']['need'] == need, result
    assert result['policy_combo'] == combo, result
    return result


def reject(candidate):
    for check in (IntakeRoleSpec.model_validate, adapter.preview):
        try:
            check(candidate)
        except (ValueError, ValidationError):
            pass
        else:
            raise AssertionError(('unsafe role accepted', candidate))


def matrix():
    # Each primary has a boundary that changes behavior, not rubric wording.
    rows = [
        ('D1', 'discovery', role('research', 'Find component symbols', facts=LOOKUP), 'bounded_retrieval', 'Small', 'writer'),
        ('D2', 'discovery', role('research', 'Map declarations with source anchors', facts=LOOKUP), 'bounded_retrieval', 'Small', 'writer'),
        ('D3', 'discovery', role('research', 'Read dependency versions and example environment names', facts=LOOKUP), 'bounded_retrieval', 'Small', 'writer'),
        ('D4', 'discovery', role('research', 'Tra endpoint theo OpenAPI version', facts=LOOKUP), 'bounded_retrieval', 'Small', 'architecture'),
        ('A1', 'architecture', role('research', 'Decide DB schema and consistency seams', 'integration_architecture', 2.5), 'integration_architecture', 'Large', 'known'),
        ('A2', 'architecture', role('research', 'Design OAuth and payment boundaries', 'integration_architecture', 2.5, risk={'authorization': True, 'payment': True}), 'integration_architecture', 'Large', 'known-risk'),
        ('A3', 'architecture', role('research', 'Design unresolved service interfaces', 'integration_architecture', 2.5, scope=[]), 'integration_architecture', 'Large', 'four-files'),
        ('A4', 'architecture', role('produce', 'Define familiar CRUD request and errors', facts=WRITER), 'everyday_implementation', 'Medium', 'architecture'),
        ('S1', 'scaffolding', role('produce', 'Generate schema from approved optional/null/default/error rules', facts=FIXED), 'repeatable_task', 'Small', 'writer'),
        ('S2', 'scaffolding', role('produce', 'Generate fixed deterministic fake seeds', facts=FIXED), 'repeatable_task', 'Small', 'writer'),
        ('S3', 'scaffolding', role('produce', 'Generate complete controller from approved template', facts=FIXED), 'repeatable_task', 'Small', 'writer'),
        ('S4', 'scaffolding', role('produce', 'Convert exact HTML to JSX under fixed fidelity and AX rules', facts=FIXED), 'repeatable_task', 'Small', 'writer'),
        ('I1', 'implementation', role('produce', 'Build UI state and handlers', facts=WRITER), 'everyday_implementation', 'Medium', 'unknown'),
        ('I2', 'implementation', role('produce', 'Implement approved backend contract', facts=WRITER, risk={'authorization': True}), 'everyday_implementation', 'Medium', 'critical-check'),
        ('I3', 'implementation', role('produce', 'Build fetch and error UI under approved contract', facts=WRITER), 'everyday_implementation', 'Medium', 'unknown'),
        ('I4', 'implementation', role('produce', 'Build linked DB API UI outcome', 'long_running_agentic', 1.5), 'long_running_agentic', 'Medium', 'architecture'),
        ('I5', 'implementation', role('produce', 'Prove isolated fixed-point financial algorithm', 'specialist', 2, capability_reason='Exact rounding invariant requires novel isolated proof', risk={'precision': True}), 'specialist', 'Large', 'known'),
        ('V1', 'verification', role('check', 'Report compiler diagnostics only', facts=CHECK), 'mechanical_verification', 'Small', 'mechanical-writer'),
        ('V2', 'verification', role('check', 'Compare schema and casing with fixed criterion', facts=CHECK), 'mechanical_verification', 'Small', 'critical-check'),
        ('V3', 'verification', role('produce', 'Write behavior tests and linked repair iterations', 'long_running_agentic', 1.5), 'long_running_agentic', 'Medium', 'mechanical-writer'),
        ('V4', 'verification', role('research', 'Find unknown stale-state root cause', facts={'unknown_cause': True}, scope=[]), 'difficult_review', 'Large', 'known'),
        ('V5', 'verification', role('produce', 'Resolve race after serious failed repair', 'specialist', 3, prior_attempt={'run': 'prior-run', 'role': 'repair-race'}), 'specialist', 'Large', 'missing-history'),
        ('O1', 'optimization', role('produce', 'Choose bounded refactor decomposition', facts=WRITER), 'everyday_implementation', 'Medium', 'prescribed'),
        ('O2', 'optimization', role('research', 'Read profiling and query plan facts', facts=LOOKUP), 'bounded_retrieval', 'Small', 'unknown'),
        ('O3', 'optimization', role('check', 'Judge authorization and data-loss invariants', 'difficult_review', 2.5, risk={'authorization': True, 'data_loss': True}), 'difficult_review', 'Large', 'lookup-risk'),
        ('C1', 'closure', role('produce', 'Fill approved changelog template with supplied facts', facts=FIXED), 'repeatable_task', 'Small', 'writer'),
        ('C2', 'closure', role('produce', 'Fill fixed PR description from supplied sanitized facts', facts=FIXED), 'repeatable_task', 'Small', 'writer'),
    ]
    assert len(rows) == 27
    for name, stage, candidate, need, combo, boundary in rows:
        candidate['stage'] = stage
        expect(candidate, need, combo)
        if boundary == 'mechanical-writer':
            reject(role('produce', 'Compile and fix semantic error', 'mechanical_verification', 0))
        elif boundary == 'critical-check':
            expect(role('check', 'Judge public contract correctness', risk={'public_contract': True}), 'difficult_review', 'Large')
        elif boundary == 'unknown':
            expect(role('research', 'Diagnose unknown cause', facts={'unknown_cause': True}, scope=[]), 'difficult_review', 'Large')
        elif boundary == 'architecture':
            expect(role('integrate', 'Decide unresolved component seams', facts={'behavior_undecided': True}), 'integration_architecture', 'Large')
        elif boundary in ('known', 'known-risk', 'four-files'):
            expect(role('produce', 'Build approved known design', 'everyday_implementation', 1.5,
                        scope=['a.py', 'b.py', 'c.py', 'd.py'], risk={'authorization': True} if boundary == 'known-risk' else {}),
                   'everyday_implementation', 'Medium')
        elif boundary == 'missing-history':
            reject(role('produce', 'Escalate without evidence', 'specialist', 3))
        elif boundary == 'prescribed':
            expect(role('produce', 'Apply exact symbol-aware rename map', facts=FIXED), 'repeatable_task', 'Small')
        elif boundary == 'lookup-risk':
            expect(role('research', 'Read approved security configuration facts only', facts=LOOKUP, risk={'security': True}), 'bounded_retrieval', 'Small')
        else:
            expect(role('produce', 'Decide schema validation, layout or new behavior', facts=WRITER), 'everyday_implementation', 'Medium')
    return len(rows)


def contracts():
    for stage in ('discovery', 'architecture', 'scaffolding', 'implementation', 'verification', 'optimization', 'closure'):
        candidate = role('produce', 'Known method across four files', 'everyday_implementation', 1,
                         stage=stage, scope=['a.py', 'b.py', 'c.py', 'd.py'])
        expect(candidate, 'everyday_implementation', 'Medium')
        assert RoleSpec.model_validate(candidate).scope == candidate['scope']
    expect(role('research', 'One-file unknown authorization bug', facts={'unknown_cause': True},
                read_scope=['auth.py'], risk={'authorization': True}), 'difficult_review', 'Large')
    for facts in (None, {}):
        for kind in ('produce', 'integrate', 'research'):
            reject(role(kind, 'Mechanical writer denied', 'mechanical_verification', 0, facts))
        for kind in ('check', 'research'):
            reject(role(kind, 'Repeatable read-only role denied', 'repeatable_task', 0, facts))
    for kind in ('check', 'research'):
        reject(role(kind, 'No write grant', 'difficult_review', 2.5, scope=['artifact.py']))
    for field in RiskFacts.model_fields:
        for value in (True, False, None):
            parsed = RoleMetadata.model_validate({'risk': {field: value}})
            assert getattr(parsed.risk, field) is value
        for value in (0, 1, 'true', 'false', [], {}):
            reject(role('check', 'Invalid risk evidence', 'difficult_review', 3, risk={field: value}))
        reject(role('check', 'Risk cannot be mechanical', 'mechanical_verification', 0, risk={field: True}))
        reject(role('check', 'Risk difficulty floor', 'difficult_review', 2.49, risk={field: True}))
        reject(role('check', 'Specialist risk difficulty floor', 'specialist', 1.99,
                    capability_reason='Isolated difficult correctness proof', risk={field: True}))
        expect(role('check', 'Intrinsic critical proof', 'specialist', 2,
                    capability_reason='Isolated difficult correctness proof', risk={field: True}), 'specialist', 'Large')
        expect(role('produce', 'Approved high-risk spec', 'everyday_implementation', 1.5,
                    risk={field: True}), 'everyday_implementation', 'Medium')
    for extra in ({'stage': 'deploy'}, {'capability_reason': ''}, {'capability_reason': '  '},
                  {'capability_reason': 1}, {'risk': {'invented': True}}, {'risk': []},
                  {'prior_attempt': {'run': 'r'}}, {'prior_attempt': {'run': '', 'role': 'r'}},
                  {'prior_attempt': {'run': 'r', 'role': 'r', 'failed': True}}):
        reject(role('produce', 'Invalid metadata', 'everyday_implementation', 1, **extra))
    for field in HOST_FIELDS:
        candidate = role('produce', 'Caller must not mint host authority', 'everyday_implementation', 1,
                         **{field: 'forged'})
        reject(candidate)
        try:
            PlanSpec.model_validate({'task': 'No authority injection', 'roles': [role('produce', 'Build', 'everyday_implementation', 1)], field: 'forged'})
        except ValidationError:
            pass
        else:
            raise AssertionError(('plan host authority accepted', field))
    for difficulty in (0, 1.99):
        reject(role('produce', 'Intrinsic capability floor', 'specialist', difficulty,
                    capability_reason='Isolated algorithmic proof'))
    legacy = role('produce', 'Existing valid specialist declaration', 'specialist', 3)
    legacy.pop('classification')
    expect(legacy, 'specialist', 'Large')
    expect(role('produce', 'Serious failed attempt', 'specialist', 3,
                prior_attempt={'run': 'historical-run', 'role': 'repair'}), 'specialist', 'Large')
    for need, difficulty in (('everyday_implementation', 1), ('repeatable_task', 0), ('specialist', 3)):
        reject(role('produce', 'Unknown cause is not a cheap edit or implicit specialist', need, difficulty,
                    facts={'unknown_cause': True}))
    reject(role('produce', 'Undecided validation is not prescribed', 'repeatable_task', 0,
                facts={'behavior_undecided': True}))
    reject(role('produce', 'Sample JSON does not fix method', 'repeatable_task', 0,
                facts={'method_fixed': False}))
    unknown = adapter.preview(role('produce', 'Only a sample, rules still unknown', stage='scaffolding'))
    assert unknown['outcome'] == 'requires_classification' and unknown['answers'] is None
    for difficulty, effort in ((0, 'low'), (0.999, 'low'), (1, 'medium'), (1.999, 'medium'), (2, 'high'), (3, 'high')):
        result = expect(role('produce', 'Approved implementation', 'everyday_implementation', difficulty), 'everyday_implementation', 'Medium')
        assert result['reasoning_effort'] == effort
        for configured in ('Low', 'Medium', 'High'):
            assert adapter.combo_effort(configured, difficulty) == configured.lower()
    # Existing Small implementation guard remains bounded and checker-dependent.
    candidate = role('produce', 'Bounded known edit', 'everyday_implementation', 1,
                     facts={'targets_fixed': True, 'behavior_fixed': True, 'scope_bounded': True,
                            'deterministic_check': True, 'behavior_undecided': False, 'unknown_cause': False,
                            'consequential_judgment': False, 'cross_system': False, 'concurrency_sensitive': False},
                     scope=['artifact.py'], inputs=['check_sdlc_routing.py'], commands=['python -B check_sdlc_routing.py'],
                     bounded_check={'input': 'check_sdlc_routing.py', 'command': 'python -B check_sdlc_routing.py'})
    root = str(Path(__file__).resolve().parent)
    assert adapter.small_routes(candidate, root)['small_route'] == 'bounded'
    for changed in ({'scope': ['a.py', 'b.py', 'c.py', 'd.py']}, {'bounded_check': None},
                    {'facts': {**candidate['facts'], 'unknown_cause': True}}):
        assert adapter.small_routes({**candidate, **changed}, root)['small_route'] is None


if __name__ == '__main__':
    # Unique absent path: no live policy, DB, key or home state is touched or created.
    isolated = str(Path(tempfile.gettempdir()) / ('sdlc-routing-' + uuid.uuid4().hex))
    with patch.dict(os.environ, {'CREWS_OMP_HOME': isolated}):
        count = matrix()
        contracts()
        assert not Path(isolated).exists()
    print(json.dumps({'status': 'PASS', 'matrix_rows': count, 'boundaries': count,
                      'contracts': 'typed metadata, kind, risk, authority, specialist, stage, effort, bounded scope',
                      'state_writes': 0}))
