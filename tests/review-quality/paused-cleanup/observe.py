import json
import sys
from flow import run
from support import Store


if len(sys.argv) != 2:
    raise ValueError("Expected exactly one JSON argument")
data = json.loads(sys.argv[1])
if (not isinstance(data, dict) or set(data) != {"enabled", "expired"}
        or any(type(value) is not bool for value in data.values())):
    raise ValueError("Expected enabled and expired booleans")
store = Store(**data)
run(store)
print(json.dumps({"payload": store.payload, "sends": store.sends}, sort_keys=True))
