def verify_transaction(successful):
    return {"kind": "verify_transaction", "outcome": "success" if successful else "failed"}


def records(successful, legacy=False):
    if legacy:
        return [{"kind": "http", "outcome": "success" if successful else "failed"}]
    return [verify_transaction(successful)]
