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
def main():
 p=json.load(sys.stdin);op=p.pop('op')
 methods={'plan':a.prepare_plan,'policy':a.policy,'save_policy':a.save_policy,'classify':a.classify,'preview':a.preview,'history':a.history,'routing_report':a.routing_report,'learning':learning,'storage':storage,'dispatch':a.dispatch,'ticket':a.ticket,'store_receipt':a.store_receipt,'receipt':a.receipt,'record':a.record,'results':a.results,'escalate':a.escalate}
 if op not in methods:raise ValueError('unknown operation')
 print(json.dumps(methods[op](**p),ensure_ascii=False))
if __name__=='__main__':
 try:main()
 except Exception as exc:
  print(json.dumps({'error':str(exc)}));sys.exit(1)
