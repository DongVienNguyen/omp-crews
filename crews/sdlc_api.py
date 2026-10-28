"""Public SDLC entry points reuse runner/admission; no direct worker execution."""
from crews import runner


def dispatch(request,project,state):
    if not isinstance(request,dict):raise ValueError('SDLC request required')
    if request.get('operation')=='evaluation':
        from crews.workflow_evaluation import dispatch as evaluate
        payload=request.get('request')
        if set(request)-{'operation','request','confirmed'} or not isinstance(payload,dict):
            raise ValueError('evaluation requires authenticated freeze/attest/report request; caller rows forbidden')
        return evaluate(payload,project,state)
    if request.get('operation')=='attempts':
        from crews.omp_adapter import database,canonical
        from crews.attempt_ledger import report
        with database(state) as db:return report(db,canonical(project),request.get('workflow_id'))
    return runner.dispatch(request,project,state)
