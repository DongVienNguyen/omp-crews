"""Private local bridge: JSON stdin/stdout, never provider credentials."""
import json,sys
sys.stdin.reconfigure(encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')
from crews import omp_adapter as a
def main():
 p=json.load(sys.stdin);op=p.pop('op')
 methods={'plan':a.prepare_plan,'policy':a.policy,'save_policy':a.save_policy,'classify':a.classify,'preview':a.preview,'history':a.history,'dispatch':a.dispatch,'ticket':a.ticket,'record':a.record,'results':a.results,'escalate':a.escalate}
 if op not in methods:raise ValueError('unknown operation')
 print(json.dumps(methods[op](**p),ensure_ascii=False))
if __name__=='__main__':
 try:main()
 except Exception as exc:
  print(json.dumps({'error':str(exc)}));sys.exit(1)
