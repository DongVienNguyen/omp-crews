"""Run with runtime-venv/Scripts/python.exe check_plan_contract.py (no network)."""
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import tempfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import ValidationError

import omp_server as server
from crews import catalog


SPEC = {
    'task': 'Inspect configuration settings',
    'roles': [{
        'name': 'inspect-settings', 'kind': 'research',
        'mission': 'Inspect configuration settings', 'deliverable': 'settings.json',
        'answers': {'need': 'bounded_retrieval', 'difficulty': 1, 'divisible': 0, 'specific': 1},
        'acceptance': ['Describe configuration settings with evidence'],
    }],
}
ANSWERS = {
    'need': {'choice': 'bounded_retrieval', 'confidence': 1, 'probabilities': {'bounded_retrieval': 1}},
    'difficulty': {'score': 1}, 'divisible': {'noul': 0}, 'needs_verifier': {'noul': 0},
}


def deref(schema, value):
    return schema['$defs'][value['$ref'].split('/')[-1]] if '$ref' in value else value

def result_data(result):
    return result.structuredContent or json.loads(next(c.text for c in result.content if hasattr(c, 'text')))



def check_schema(schema):
    spec = deref(schema, schema['properties']['spec'])
    assert {'task', 'roles'} <= set(spec.get('required', [])), 'spec must expose required task and roles'
    role = deref(schema, spec['properties']['roles']['items'])
    assert {'name', 'kind', 'mission', 'answers', 'deliverable'} <= set(role['required'])
    assert set(role['properties']['kind']['enum']) == {'research', 'produce', 'integrate', 'check'}
    answer = deref(schema, role['properties']['answers'])
    assert set(answer['properties']['need']['enum']) == set(catalog.load()['needs'])
    assert answer['properties']['difficulty']['minimum'] == 0
    assert answer['properties']['difficulty']['maximum'] == 3
    assert answer['properties']['divisible']['maximum'] == 1
    task_answer = deref(schema, schema['properties']['answers'])
    need = deref(schema, task_answer['properties']['need'])
    assert need['properties']['confidence']['maximum'] == 1
    difficulty = deref(schema, task_answer['properties']['difficulty'])
    assert difficulty['properties']['score']['maximum'] == 3


async def main():
    tools = await server.mcp.list_tools()
    check_schema(next(t.inputSchema for t in tools if t.name == 'crew_plan'))
    with tempfile.TemporaryDirectory() as state:
        old_home = os.environ.get('CREWS_OMP_HOME')
        os.environ['CREWS_OMP_HOME'] = state
        try:
            plan_spec = server.PlanSpec.model_validate(SPEC)
            task_answers = server.TaskAnswers.model_validate(ANSWERS)
            direct = server.crew_plan(plan_spec, task_answers, state, 'typed-contract')
            call = direct['waves'][0]['calls'][0]
            assert (call['model'], call['reasoning_effort'], call['policy_combo']) == ('code-seek', 'medium', 'Small')
            legacy = dict(SPEC, need='bounded_retrieval', difficulty=1, divisible=0, needs_verifier=0)
            legacy_result = server.crew_plan(legacy, {}, state, 'legacy-contract')
            assert legacy_result['budget'] == direct['budget']
            rich = deepcopy(SPEC)
            role = rich['roles'][0]
            role.update(commands=['python --version'], authority=['Use settings source'],
                        inputs=['settings.py'], criteria=['Evidence names settings source'],
                        execution=['Read settings source'], blocked_when=['Source unavailable'],
                        must_not=['Change source'], read_scope=['settings.py'],
                        finding_format='Cite settings source', returns='report',
                        professional_frame={'profession': 'Configuration analyst'})
            rich.update(force={'roles': {}}, allow=2)
            assert server.PlanSpec.model_validate(rich).model_dump(exclude_unset=True) == rich
            rendered = server.crew_plan(server.PlanSpec.model_validate(rich), task_answers, state, 'rich-contract')
            rich_call = rendered['waves'][0]['calls'][0]
            assert rich_call['commands'] == ['python --version']
            assert 'Use settings source' in rich_call['prompt']
            assert 'Describe configuration settings with evidence' in rich_call['prompt']
            bad = {'goal': SPEC['task'], 'roles': [{'id': 'inspect-settings', 'task': SPEC['task']}]}
            try:
                server.crew_plan(bad, {}, state, 'bad-contract')
            except ValidationError as exc:
                locations = {e['loc'] for e in exc.errors()}
                assert {('spec', 'task'), ('spec', 'roles', 0, 'name'),
                        ('spec', 'roles', 0, 'kind'), ('spec', 'roles', 0, 'mission'),
                        ('spec', 'roles', 0, 'answers')} <= locations, locations
            else:
                raise AssertionError('Malformed canonical spec accepted')
            typo_answers = deepcopy(ANSWERS)
            typo_answers['need']['probabilites'] = {'bounded_retrieval': 1}
            try:
                server.crew_plan(SPEC, typo_answers, state, 'typo-contract')
            except ValidationError as exc:
                assert ('answers', 'need', 'probabilites') in {e['loc'] for e in exc.errors()}
            else:
                raise AssertionError('Misspelled classification field accepted')
            for path, value in [('need', 'invented_need'), ('difficulty', 3.1),
                                ('difficulty', True), ('divisible', -0.1), ('specific', 1.1)]:
                invalid = deepcopy(SPEC)
                invalid['roles'][0]['answers'][path] = value
                try:
                    server.crew_plan(invalid, ANSWERS, state, 'invalid-range')
                except ValidationError as exc:
                    assert ('spec', 'roles', 0, 'answers', path) in {e['loc'] for e in exc.errors()}
                else:
                    raise AssertionError(f'Invalid role answers.{path} accepted: {value!r}')
            for field, key, value in [('need', 'choice', 'invented_need'),
                                      ('need', 'confidence', 1.1), ('difficulty', 'score', -1),
                                      ('divisible', 'noul', 2), ('needs_verifier', 'noul', True)]:
                invalid_answers = deepcopy(ANSWERS)
                invalid_answers[field][key] = value
                try:
                    server.crew_plan(SPEC, invalid_answers, state, 'invalid-task-range')
                except ValidationError as exc:
                    assert ('answers', field, key) in {e['loc'] for e in exc.errors()}
                else:
                    raise AssertionError(f'Invalid task answers.{field}.{key} accepted')
            conflict = dict(legacy, need='specialist')
            explicit = server.PlanArguments.model_validate({'spec': conflict, 'answers': ANSWERS,
                'project': state, 'session': 'explicit-answers'})
            assert explicit.answers.need.choice == 'bounded_retrieval'
            assert explicit.spec.model_extra['need'] == 'specialist'
            assert legacy['need'] == 'bounded_retrieval' and 'need' not in SPEC
            params = StdioServerParameters(command=sys.executable,
                args=[str(Path(server.__file__).resolve())],
                env={**os.environ, 'CREWS_OMP_HOME': state, 'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1'})
            async with stdio_client(params) as (reader, writer):
                async with ClientSession(reader, writer) as client:
                    await client.initialize()
                    listed = await client.list_tools()
                    check_schema(next(t.inputSchema for t in listed.tools if t.name == 'crew_plan'))
                    info = await client.call_tool('crew_catalog', {})
                    data = result_data(info)
                    cat = catalog.load()
                    assert data['questions'] == cat['questions']
                    assert data['thresholds'] == cat['thresholds']
                    assert data['kind_columns'] == {k: v['column'] for k, v in cat['kinds'].items()}
                    assert set(data['model_policy']['combos']) == {'Small', 'Medium', 'Large'}
                    assert data['combo_effort_options'] == ['Low', 'Medium', 'High', 'Auto']
                    assert data['classifier_model'] == '9router/code-astra:high'
                    assert 'seek_first_policy' not in data
                    assert data['effort_policy']
                    example = data['minimal_example']
                    result = await client.call_tool('crew_plan', {**example, 'project': state, 'session': 'mcp-contract'})
                    assert not result.isError, result
                    assert result_data(result)['task'] == example['spec']['task']
                    legacy_result = await client.call_tool('crew_plan', {'spec': legacy, 'answers': {},
                        'project': state, 'session': 'mcp-legacy'})
                    assert not legacy_result.isError, legacy_result
                    invalid_result = await client.call_tool('crew_plan', {'spec': bad, 'answers': {},
                        'project': state, 'session': 'mcp-invalid'})
                    assert invalid_result.isError, invalid_result
                    error = '\n'.join(c.text for c in invalid_result.content if hasattr(c, 'text'))
                    for location in ('spec.task', 'spec.roles.0.name', 'spec.roles.0.kind',
                                     'spec.roles.0.mission', 'spec.roles.0.answers'):
                        assert location in error, error
                    assert 'KeyError' not in error, error
        finally:
            if old_home is None:
                os.environ.pop('CREWS_OMP_HOME', None)
            else:
                os.environ['CREWS_OMP_HOME'] = old_home
    print('plan contract: typed calls, passthrough, legacy normalization, MCP schema/catalog/errors PASS')


if __name__ == '__main__':
    asyncio.run(main())
