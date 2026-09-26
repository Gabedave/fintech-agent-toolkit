def classify(records):
    for record in records:
        if record["kind"] == "http" and record["outcome"] == "success":
            return "review_required"
    return "terminal_failed"
