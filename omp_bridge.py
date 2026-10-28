"""Private local bridge: JSON stdin/stdout, never provider credentials."""
import json,sys
sys.stdin.reconfigure(encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')
from crews import omp_adapter as a
def learning(args,project=None):
 from crews.learning import dispatch
 return dispatch(args,project)
def storage(args):
 from crews.storage import dispatch
 return dispatch(args)
def recipes(args,project=None):
 from crews.recipes import dispatch
 return dispatch(args,project)
def automation(request,project):
 from crews.automation import dispatch
 return dispatch(request,project)
def automation_next(project):
 from crews.automation import next_review
 return next_review(project)
def automation_finish(job_id,project):
 from crews.automation import finish
 return finish(job_id,project)
def automation_schema():
 from crews.automation import governance_schema
 return governance_schema()
def automation_ensure(project):
 from crews.automation import ensure
 return ensure(project)
def shape(request,project):
 from crews.shaping import propose
 return propose(request,project)
def account(request,project):
 from crews.accounting import attest
 return attest(request,project,a.home())
def evaluate(request,project):
 from crews.evaluation import dispatch
 return dispatch(request,project,a.home())
def runner(request,project):
 from crews.runner import dispatch
 return dispatch(request,project,a.home())
def main():
 p=json.load(sys.stdin);op=p.pop('op')
 methods={'plan':a.prepare_plan,'policy':a.policy,'save_policy':a.save_policy,'classify':a.classify,'preview':a.preview,'history':a.history,'routing_report':a.routing_report,'learning':learning,'storage':storage,'dispatch':a.dispatch,'ticket':a.ticket,'store_receipt':a.store_receipt,'receipt':a.receipt,'record':a.record,'results':a.results,'escalate':a.escalate}
 methods.update(recover=a.recover,recipes=recipes,shape=shape,account=account,evaluate=evaluate,runner=runner,store_tool_receipt=a.store_tool_receipt,tool_receipts=a.tool_receipts,verify_profile=a.verify_profile)
 methods.update(automation=automation,automation_next=automation_next,automation_finish=automation_finish,automation_schema=automation_schema,automation_ensure=automation_ensure)
 if op not in methods:raise ValueError('unknown operation')
 print(json.dumps(methods[op](**p),ensure_ascii=False))
if __name__=='__main__':
 try:main()
 except Exception as exc:
  print(json.dumps({'error':str(exc)}));sys.exit(1)
