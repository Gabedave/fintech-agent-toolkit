def classify(records):
    for record in records:
        if record["kind"] in {"http", "verify_transaction"} and record["outcome"] == "success":
            return "review_required"
    return "terminal_failed"
