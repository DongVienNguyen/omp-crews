from copy import deepcopy
from tempfile import TemporaryDirectory
from crews.shaping import propose


def run():
 with TemporaryDirectory() as project:
  invariant='unchanged surrounding behavior'
  writer={'name':'mapping-writer','kind':'produce','mission':'Fix mapping','deliverable':'out.py','scope':['out.py'],'inputs':['in.py'],'commands':[],'acceptance':[invariant],'answers':{'need':'everyday_implementation','difficulty':1,'divisible':0,'specific':1}}
  check={'name':'mapping-check','kind':'check','mission':'Verify mapping','deliverable':'verdict','scope':[],'inputs':['out.py'],'commands':[],'criteria':[invariant],'answers':{'need':'mechanical_verification','difficulty':1,'divisible':0,'specific':1}}
  request={'task':'Fix mapping','authority':{'read':['in.py'],'write':['out.py'],'commands':[]},'invariants':[invariant],'roles':[writer,check]}
  output=propose(request,project)
  assert output['admitted'] is False and output['spec']['roles'][0]['scope']==['out.py']
  assert request['roles'][0]['scope']==['out.py']
  for mutate in [lambda p:p['roles'][0].update(scope=['secret.py']),lambda p:p['roles'][0].update(commands=['rm -rf /']),lambda p:p['roles'][1].update(criteria=['unrelated']),lambda p:p['roles'][1].update(inputs=[]),lambda p:p['roles'].append(deepcopy(writer)),lambda p:p['roles'][1].update(scope=['out.py'])]:
   invalid=deepcopy(request);mutate(invalid)
   try:propose(invalid,project)
   except ValueError:pass
   else:raise AssertionError('invalid authority or invariant proposal accepted')
 print('PASS: task shaping preserves caller authority, independent invariants and proposal-only boundary')


if __name__=='__main__':run()
