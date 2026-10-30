import json
import tempfile
from pathlib import Path
from crews import omp_adapter as a


def check():
 with tempfile.TemporaryDirectory() as temporary:
  root=Path(temporary);project=root/'project';project.mkdir();state=root/'state'
  empty=a.routing_report(str(project),state)
  assert empty['calls']==0 and empty['native_usage']=={}
  assert not state.exists()
  assert all(value=={'known':0,'unknown':0} for value in empty['native_usage_coverage'].values())
  cells=[{'role_id':'first','requested_combo':'Medium','effective_combo':'Small','bounded_small':True,'classification':{'outcome':'declared'},'prompt':'PRIVATE_PROMPT'},
         {'role_id':'second','policy_combo':'Medium','candidate_route':'routine','blocked_by':['explicit_floor:Medium'],'policy_source':'legacy_force_preserve','dispatch_entry':'intake','classification':{'outcome':'teacher'}},
         {'role_id':'third'}]
  with a.database(state) as db:
   db.execute('INSERT INTO runs VALUES(?,?,?,?,?)',('run',a.canonical(str(project)),'session',0,json.dumps({'waves':[{'calls':cells}]})))
   db.execute('INSERT INTO runs VALUES(?,?,?,?,?)',('other',str(root/'other'),'session',0,json.dumps({'waves':[]})))
   results=[{'native':{'usage':{'inputTokens':10,'outputTokens':0},'durationMs':25}},
            {'native':{'resolvedModel':'fixture/medium','usage':{'input':False,'output':float('inf'),'durationMs':-1}}},None]
   for cell,status,result in zip(cells,['completed','failed','planned'],results):
    db.execute('INSERT INTO calls VALUES(?,?,?,?,?)',('run',cell['role_id'],'private',status,json.dumps(result) if result else None))
   db.execute('INSERT INTO attempts VALUES(?,?,?,?)',('run','first',2,1))
   db.execute('INSERT INTO attempts VALUES(?,?,?,?)',('other','ignored',99,99))
  before=(state/'runs.sqlite').read_bytes()
  report=a.routing_report(str(project),state)
  assert report['runs']==1 and report['calls']==3
  assert report['by_requested_combo']=={'Medium':2,'unknown':1}
  assert report['by_effective_combo']==report['by_combo']=={'Small':1,'Medium':1,'unknown':1}
  assert report['by_status']=={'completed':1,'failed':1,'planned':1}
  assert report['by_source']=={'declared':1,'teacher':1,'unknown':1}
  assert report['attempts']=={'repairs':1,'escalations':2}
  assert report['bounded_small']==1
  assert report['by_blocked_by']=={'explicit_floor:Medium':1}
  assert report['by_executed_route']=={'forced_floor':1}
  assert report['by_entry']['intake']==1 and report['unpersisted_populations']['native_task']=='unknown_not_rerouted'
  assert report['native_usage']=={'input':10,'output':0,'durationMs':25}
  assert all(value=={'known':1,'unknown':2} for value in report['native_usage_coverage'].values())
  assert 'PRIVATE_PROMPT' not in json.dumps(report) and 'private' not in json.dumps(report)
  assert (state/'runs.sqlite').read_bytes()==before
  try:a.routing_report(str(root/'missing'),state)
  except ValueError:pass
  else:raise AssertionError('missing project accepted')
 print('routing report checks passed')


if __name__=='__main__':check()
