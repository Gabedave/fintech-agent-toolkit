"""Pure conjunction of already admitted evidence, without an admission policy.

Callers must authenticate identity, raw evidence, reviewer origin, and retained
history before passing statuses here. A mutable status string is not proof.
"""


def combine(action_status, claim_status, *, admitted_failure=False,
            operational_incomplete=False):
    if admitted_failure or action_status == 'fail' or claim_status == 'fail':
        return 'fail'
    if (action_status in {'eligible', 'pass'} and claim_status == 'pass'
            and not operational_incomplete):
        return 'pass'
    return 'incomplete'
