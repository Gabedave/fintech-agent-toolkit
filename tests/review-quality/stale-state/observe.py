import json
import sys
from flow import run
from support import Store


if len(sys.argv) != 2:
    raise ValueError("Expected exactly one JSON argument")
data = json.loads(sys.argv[1])
if (not isinstance(data, dict) or set(data) != {"card", "restore_card"}
        or type(data["restore_card"]) is not bool
        or not (data["card"] is None or isinstance(data["card"], str) and data["card"])):
    raise ValueError("Expected card (null/nonempty string) and restore_card (boolean)")
store = Store(**data)
state = run(store)
print(json.dumps({"state": state, "card": store.plan["card"], "debits": store.debits}, sort_keys=True))
