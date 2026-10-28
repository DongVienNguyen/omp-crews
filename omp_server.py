from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError, model_validator
from mcp.server.fastmcp.utilities.func_metadata import ArgModelBase
from mcp.server.fastmcp import FastMCP
from crews import omp_adapter as a,catalog
from crews.classification import ClassificationFacts, HOST_FIELDS, RoleMetadata, RUBRIC, policy_version, safety_errors

Need = Literal[tuple(catalog.load()['needs'])]
Unit = Annotated[float, Field(strict=True, ge=0, le=1)]
Difficulty = Annotated[float, Field(strict=True, ge=0, le=3)]
Text = Annotated[str, Field(min_length=1, pattern=r'\S')]


class NeedAnswer(BaseModel):
 model_config = ConfigDict(extra='forbid')
 choice: Need
 confidence: Unit
 probabilities: dict[Need, Unit] = Field(default_factory=dict)


class NoulAnswer(BaseModel):
 model_config = ConfigDict(extra='forbid')
 noul: Unit


class DifficultyAnswer(BaseModel):
 model_config = ConfigDict(extra='forbid')
 score: Difficulty


class TaskAnswers(BaseModel):
 """Task-level classification; role classifications use flat RoleAnswers instead."""
 model_config = ConfigDict(extra='forbid')
 need: NeedAnswer
 difficulty: DifficultyAnswer
 divisible: NoulAnswer
 needs_verifier: NoulAnswer


class RoleAnswers(BaseModel):
 model_config = ConfigDict(extra='forbid')
 need: Need
 difficulty: Difficulty
 divisible: Unit
 specific: Unit | None = None


class BoundedCheck(BaseModel):
 model_config = ConfigDict(extra='forbid')
 input: Text
 command: Text

class CheckerProfile(BoundedCheck):
 version: Text


class RoleSpec(RoleMetadata):
 """Canonical role identity and classification; upstream validates execution constraints."""
 model_config = ConfigDict(extra='allow')
 name: Annotated[str, Field(pattern=r'^[a-z0-9]+(-[a-z0-9]+)*$')]
 kind: Literal['research', 'produce', 'integrate', 'check']
 mission: Text
 deliverable: Text
 answers: RoleAnswers
 solution_space: Text | None = None
 facts: ClassificationFacts | None = None
 context_request: StrictBool = False
 bounded_check: BoundedCheck | None = None
 routine_check: Annotated[str, Field(pattern=r'^[a-z0-9]+(-[a-z0-9]+)*$')] | None = None
 checker_profile: CheckerProfile | None = None
 verify_targets: list[Text] = Field(default_factory=list)
 evidence_unit: Text | None = None
 recipe_features: dict[str,Text] | None = None
 recipe_profile: BoundedCheck | None = None
 model_revision: Text | None = None
 recipe_confirmed: StrictBool = False
 recipe_approval: dict | None = None
 recipe_id: Text | None = None
 scope: list[Text] = Field(default_factory=list)
 commands: list[Text] = Field(default_factory=list)
 authority: list[Text] | None = None
 inputs: list[Text] | None = None
 acceptance: list[Text] | None = None
 criteria: list = Field(default_factory=list)
 execution: list[Text] | None = None
 blocked_when: list[Text] | None = None
 must_not: list[Text] | None = None
 read_scope: list[Text] | None = None
 finding_format: Text | None = None
 returns: Literal['artifact', 'report'] | None = None
 professional_frame: dict | None = None
 slices: list[dict] = Field(default_factory=list)

 @model_validator(mode='before')
 @classmethod
 def reject_host_authority(cls, value):
  if isinstance(value, dict) and HOST_FIELDS.intersection(value):
   raise ValueError('reserved host authority fields: ' + ', '.join(sorted(HOST_FIELDS.intersection(value))))
  return value

 @model_validator(mode='after')
 def validate_safety(self):
  errors=safety_errors(self.model_dump(exclude_unset=True))
  if errors:
   raise ValidationError.from_exception_data(type(self).__name__,[
    {'type':'value_error','loc':loc,'input':self.model_dump(exclude_unset=True),
     'ctx':{'error':ValueError(message)}} for loc,message in errors])
  return self


class PlanSpec(BaseModel):
 model_config = ConfigDict(extra='allow')
 task: Text
 roles: Annotated[list[RoleSpec], Field(min_length=1)]

 @model_validator(mode='before')
 @classmethod
 def reject_host_authority(cls, value):
  if isinstance(value, dict) and HOST_FIELDS.intersection(value):
   raise ValueError('reserved host authority fields: ' + ', '.join(sorted(HOST_FIELDS.intersection(value))))
  return value


class PlanArguments(ArgModelBase):
 spec: PlanSpec
 answers: TaskAnswers
 project: str
 session: str

 @model_validator(mode='before')
 @classmethod
 def normalize_legacy(cls, value):
  if not isinstance(value, dict) or value.get('answers'):
   return value
  spec = value.get('spec')
  if isinstance(spec, PlanSpec):
   spec = spec.model_dump(exclude_unset=True)
  if not isinstance(spec, dict) or not isinstance(spec.get('need'), str):
   return value
  need = spec['need']
  return {**value,
   'answers': {
    'need': {'choice': need, 'confidence': 1, 'probabilities': {need: 1}},
    'difficulty': {'score': spec.get('difficulty', 1)},
    'divisible': {'noul': spec.get('divisible', 0)},
    'needs_verifier': {'noul': spec.get('needs_verifier', 0)},
   },
   'spec': {key: item for key, item in spec.items()
            if key not in {'need', 'difficulty', 'divisible', 'needs_verifier'}}}

class IntakeRoleAnswers(BaseModel):
 """Only auto intake can leave need/difficulty unresolved."""
 model_config = ConfigDict(extra='forbid')
 need: Need | None = None
 difficulty: Difficulty | None = None
 divisible: Unit
 specific: Unit | None = None


class IntakeRoleSpec(RoleSpec):
 answers: IntakeRoleAnswers
 classification: StrictBool = False

 @model_validator(mode='after')
 def validate_intake(self):
  from crews.classification import answer_errors
  errors=answer_errors(self.model_dump(exclude_unset=True),require_complete=not self.classification)
  if errors:
   raise ValidationError.from_exception_data(type(self).__name__,[
    {'type':'value_error','loc':loc,'input':self.model_dump(exclude_unset=True),
     'ctx':{'error':ValueError(message)}} for loc,message in errors])
  return self


class IntakePlanSpec(PlanSpec):
 roles: Annotated[list[IntakeRoleSpec], Field(min_length=1)]


class IntakePlanArguments(PlanArguments):
 spec: IntakePlanSpec


def minimal_example():
 return {
  'spec': {'task': 'Inspect configuration settings', 'roles': [{
   'name': 'inspect-settings', 'kind': 'research',
   'mission': 'Inspect configuration settings', 'deliverable': 'settings.json',
   'acceptance': ['Describe configuration settings with evidence'],
   'answers': {'need': 'bounded_retrieval', 'difficulty': 1, 'divisible': 0, 'specific': 1},
  }]},
  'answers': {'need': {'choice': 'bounded_retrieval', 'confidence': 1,
                       'probabilities': {'bounded_retrieval': 1}},
              'difficulty': {'score': 1}, 'divisible': {'noul': 0},
              'needs_verifier': {'noul': 0}},
 }


mcp=FastMCP('crews-omp',log_level='ERROR')
@mcp.tool()
def crew_catalog()->dict:
 cat = catalog.load()
 policy=a.model_policy()
 classification_policy={'rubric':RUBRIC,'facts_schema':ClassificationFacts.model_json_schema(),'auto_intake_schema':IntakePlanArguments.model_json_schema()}
 classification_policy['bounded_implementation']=a.BOUNDED_ROUTE
 classification_policy['routine_implementation']={**a.BOUNDED_ROUTE,'max_difficulty':1,'true_facts':[key for key in a.BOUNDED_ROUTE['true_facts'] if key!='deterministic_check'],'check':'routine_check names an independent read-only check role, carrying original acceptance and artifact inputs, dispatched in a later wave; executable checker inputs outside every writer scope'}
 return {'combos':policy['combos'],'model_policy':policy,'classifier_model':a.policy()['classifier_model'],'policy_version':policy_version(),'classification_policy':classification_policy,'combo_effort_options':['Low','Medium','High','Auto'],'effort_policy':{'auto':'difficulty: [0,1) low; [1,2) medium; [2,3] high','selection':{'Small':['mechanical_verification','repeatable_task','bounded_retrieval'],'Medium':['everyday_implementation','long_running_agentic'],'Large':['difficult_review','integration_architecture','specialist']}},'needs':list(cat['needs']),'questions':cat['questions'],'kind_columns':{kind:details['column'] for kind,details in cat['kinds'].items()},'thresholds':cat['thresholds'],'minimal_example':minimal_example(),'guard':'native wrapper plus extension checks; not OS sandbox','concurrency':2,'depth':1}


@mcp.tool()
def crew_plan(spec:PlanSpec,answers:TaskAnswers,project:str,session:str)->dict:
 """Plan canonical {task, roles} with nested task answers and flat per-role answers."""
 args = PlanArguments.model_validate({'spec': spec, 'answers': answers,
                                      'project': project, 'session': session})
 return a.build_plan(args.spec.model_dump(exclude_unset=True),
                     args.answers.model_dump(exclude_unset=True), args.project, args.session)


# Normalize legacy sibling arguments before FastMCP validates the nested models.
_plan_tool = mcp._tool_manager.get_tool('crew_plan')
_plan_tool.fn_metadata.arg_model = PlanArguments
_plan_tool.parameters = PlanArguments.model_json_schema()
@mcp.tool()
def crew_results(run:str,project:str,session:str)->list:
 return a.results(run,project,session)
@mcp.tool()
def crew_escalate(run:str,role:str,reason:str,project:str,session:str,repair:bool=False)->dict:
 return a.escalate(run,role,reason,project,session,repair)

@mcp.tool()
def crew_test(role:dict,project:str|None=None)->dict:
 """Deterministic role classification and actual seat preview; no state or admission."""
 return a.preview(role,project)

@mcp.tool()
def crew_history(project:str,limit:Annotated[int,Field(strict=True,ge=1,le=200)]=50)->list:
 """Project-scoped recent run/role status and routing only; prompts omitted."""
 return a.history(project,limit)
@mcp.tool()
def crew_routing_report(project:str)->dict:
 """Read-only project routing counts and native usage; no prompts or commands."""
 return a.routing_report(project)

@mcp.tool()
def crew_recover(run:str,role:str,project:str,session:str,reason:Text,confirmed:StrictBool=False)->dict:
 """Explicitly reconcile a dead dispatch owner; never claim completion or replay."""
 return a.recover(run,role,project,session,reason,confirmed)

@mcp.tool()
def crew_recipes(request:dict,project:str)->dict:
 """Recipe candidates, verified evidence and explicit consented lifecycle."""
 from crews.recipes import dispatch
 return dispatch(request,project)

@mcp.tool()
def crew_automation(request:dict,project:str)->dict:
 """Keyless local automation status/enable/disable; policy changes require independent Large host-verified review."""
 from crews.automation import dispatch
 return dispatch(request,project)

@mcp.tool()
def crew_shape(request:dict,project:str)->dict:
 """Validate caller-scoped role proposal; never admit or invent authority."""
 from crews.shaping import propose
 return propose(request,project)

@mcp.tool()
def crew_account(request:dict,project:str)->dict:
 """Record operator-signed complete run accounting; never infer unknown prices."""
 from crews.accounting import attest
 return attest(request,project,a.home())

@mcp.tool()
def crew_evaluate(request:dict,project:str)->dict:
 from crews.evaluation import dispatch
 return dispatch(request,project,a.home())

@mcp.tool()
def crew_runner(request:dict,project:str)->dict:
 from crews.sdlc_api import dispatch
 return dispatch(request,project,a.home())

@mcp.tool()
def crew_storage(request:dict)->dict:
 from crews.storage import dispatch
 if (request.get('operation')=='compact' or request.get('operation')=='cleanup' and request.get('dry_run') is False) and request.get('confirmed') is not True:raise ValueError('storage mutation requires explicit confirmation')
 return dispatch({k:v for k,v in request.items() if k!='confirmed'},a.home())

if __name__=='__main__':mcp.run(transport='stdio')
