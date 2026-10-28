"""Independent criterion outcomes cannot poison unrelated writers or reset via names."""
import tempfile
from crews import omp_adapter as a, attempt_ledger as ledger
from check_effort_policy import isolated_home, rejects


def run():
    with tempfile.TemporaryDirectory() as folder, isolated_home(folder), a.database(folder) as db:
        project=a.canonical(folder)
        def writer(name,criterion):return dict(role_id=name,policy_combo='Medium',write_scope=[name+'.txt'],acceptance=[criterion],role_answers=dict(need='everyday_implementation'))
        left=writer('left','Left value correct');right=writer('right','Right value correct')
        for i in range(3):
            run='run'+str(i)
            for cell in (left,right):ledger.record(db,run,cell['role_id'],project,cell,dict(status='COMPLETE'))
            checker=dict(role_id='check',policy_combo='Small',write_scope=[],acceptance=left['acceptance']+right['acceptance'],verify_targets=['left','right'])
            verdicts=[dict(criterion='Left value correct',status='pass'),dict(criterion='Right value correct',status='fail')]
            ledger.record(db,run,'check',project,checker,dict(host_authenticated=True,outcome=dict(behavior='fail',verification=dict(criteria=verdicts))))
        assert ledger.strikes(db,project,left)==0
        assert ledger.strikes(db,project,right)==2
        renamed={**right,'role_id':'renamed','role_answers':dict(need='specialist')}
        assert ledger.fault_key(renamed)==ledger.fault_key(right)
        rejects(lambda:ledger.guard(db,project,renamed),'two behavioral')
        reordered={**right,'acceptance':['B','A']};assert ledger.fault_key(reordered)==ledger.fault_key({**reordered,'acceptance':['A','B']})
        ledger.guard(db,project,left)
        print('PASS cross-run repair lineage, renamed need/order stability, criterion-specific two-strike, unrelated writer remains eligible')

if __name__=='__main__':run()
