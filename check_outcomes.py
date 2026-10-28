"""Isolated consumer-visible verified behavior and interrupted-admission checks."""
import copy,json,os,subprocess,sys,tempfile
from pathlib import Path
from crews import omp_adapter as a,outcomes
from check_effort_policy import isolated_home,task_answers


def rejects(fn,fragment=None):
    try:fn()
    except ValueError:return
    else:raise AssertionError('expected refusal')


def run():
    with tempfile.TemporaryDirectory(prefix='crews-outcome-') as folder,isolated_home(folder):
        p=Path(folder);(p/'out.py').write_text('value=1\n');(p/'verify.py').write_text('from out import value\nassert value==1\n')
        command=sys.executable.replace('\\','/')+' -B verify.py';criterion='normal and missing/null boundary preserved'
        (p/'verify.py').write_text('import json\nfrom out import value\nassert value==1\nprint(json.dumps({"criterion_results":[{"criterion":'+repr(criterion)+',"status":"pass"}]}))\n')
        writer={'name':'writer','kind':'produce','mission':'Implement fixed value behavior','deliverable':'out.py','scope':['out.py'],'inputs':['out.py'],'commands':[],'acceptance':[criterion],'evidence_unit':'unit-a','answers':{'need':'everyday_implementation','difficulty':1,'divisible':0,'specific':1}}
        checker={'name':'value-checker','kind':'check','mission':'Verify fixed value behavior','deliverable':'verdict','scope':[],'inputs':['out.py','verify.py'],'commands':[command],'criteria':[criterion],'verify_targets':['writer'],'checker_profile':{'input':'verify.py','command':command,'version':'1'},'answers':{'need':'mechanical_verification','difficulty':1,'divisible':0,'specific':1}}
        plan=a.build_plan({'task':'Implement fixed value behavior','roles':[writer,checker]},task_answers('everyday_implementation',1,True),folder,'proof',folder)
        calls={c['role_id']:c for w in plan['waves'] for c in w['calls']}
        calls['verifier']=calls['value-checker']
        def complete(role,claim='COMPLETE',criteria=None):
            if role=='verifier':role='value-checker'
            ticket=a.dispatch(plan['run_id'],role,folder,'proof',folder);cell=ticket['call'];token=ticket['token']
            receipt={'token':token,'role':role,'provider':cell['provider'],'model':cell['model'],'effort':cell['reasoning_effort']}
            a.store_receipt(token,folder,receipt,folder)
            if cell.get('checker_profile'):assert a.verify_profile(token,folder,folder,host_key=ticket['host_key'])['receipt']['exit_code']==0
            native={'exitCode':0,'resolvedModel':cell['provider']+'/'+cell['model']+':'+cell['reasoning_effort'],'resolvedThinkingLevel':cell['reasoning_effort'],'durationMs':10,'usage':{'input':4,'output':2}}
            result={'status':claim,'producer_claim':claim,'verification':['observed independent contract'],'native':native,'wire':receipt,'criterion_results':criteria}
            a.record(plan['run_id'],role,result,folder,'proof',folder,host_key=ticket['host_key'])
            return token
        complete('writer')
        # Caller-provided fake receipt cannot satisfy authoritative host ledger.
        raw={'status':'COMPLETE','native':{'exitCode':0,'resolvedModel':'9router/code-seek:medium','resolvedThinkingLevel':'medium'},'wire':{'provider':'9router','model':'code-seek','effort':'medium','role':'verifier'},'criterion_results':[{'criterion':criterion,'status':'pass'}],'tool_receipts':[]}
        assert outcomes.derive(calls['verifier'],raw,folder)['behavior']=='unknown'
        forged=copy.deepcopy(raw);forged['wire']['role']='value-checker'
        forged['tool_receipts']=[{'tool':'bash','command':command,'exit_code':0,'error':False,'tool_call_id':'host-verify-fake'}]
        assert outcomes.derive(calls['verifier'],forged,folder)['behavior']=='unknown'
        token=complete('verifier',criteria=[{'criterion':criterion,'status':'pass'}])
        proof=outcomes.verified_pair(plan['run_id'],'writer','value-checker',folder,folder)
        assert proof['verified'] and proof['behavior']=='pass' and proof['execution']['cost'] is None
        rejects(lambda:a.ticket(token,folder,folder))
        result=a.results(plan['run_id'],folder,'proof',folder)
        producer=next(r['result'] for r in result if r['role_id']=='writer')
        assert producer['outcome']['independent_behavior']=='pass' and producer['outcome']['claim_contradicted'] is False
        (p/'out.py').write_text('value=2\n')
        rejects(lambda:outcomes.verified_pair(plan['run_id'],'writer','value-checker',folder,folder),'stale')
        # A stopped dispatch cannot be replayed or reconciled while owner still lives.
        plan2=a.build_plan({'task':'Implement fixed value behavior','roles':[writer]},task_answers('everyday_implementation',1),folder,'recover',folder)
        child=subprocess.run([sys.executable,'-B','-c',"import sys;from crews import omp_adapter as a;a.dispatch(sys.argv[1],'writer',sys.argv[2],'recover',sys.argv[2])",plan2['run_id'],folder],cwd=Path(__file__).parent,capture_output=True,text=True)
        assert child.returncode==0,child.stderr
        rejects(lambda:a.recover(plan2['run_id'],'writer',folder,'recover','operator requested',False,folder),'confirmation')
        assert a.recover(plan2['run_id'],'writer',folder,'recover','owner subprocess exited',True,folder)['execution']=='interrupted'
        rejects(lambda:a.dispatch(plan2['run_id'],'writer',folder,'recover',folder),'unplanned')
        assert a.results(plan2['run_id'],folder,'recover',folder)[0]['result']['outcome']['behavior']=='unknown'
        # Fail behavior is not turned into verified success by COMPLETE text.
        cell=calls['verifier'];bad=copy.deepcopy(raw)
        bad['wire']['role']='value-checker'
        bad['tool_receipts']=[{'tool':'bash','command':command,'exit_code':1,'error':True,'tool_call_id':'host-verify-fixture','source':'host_profile','role':'value-checker','profile_hash':outcomes.digest(cell['checker_profile']),'artifacts':outcomes.fingerprints(folder,cell['write_scope']+cell['read_scope'])}]
        bad['tool_receipts'][0]['criterion_results']=[{'criterion':criterion,'status':'fail'}]
        assert outcomes.derive(cell,bad,folder)['behavior']=='fail'
        assert outcomes.derive(cell,bad,folder)['execution']=='tool_error'
    print('PASS: executable behavior, stale artifacts, cost unknown, claim independence, dead-owner recovery and no replay')


if __name__=='__main__':run()
