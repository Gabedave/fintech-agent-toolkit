import json
import sys
from flow import classify
from support import records


if len(sys.argv) != 2:
    raise ValueError("Expected exactly one JSON argument")
data = json.loads(sys.argv[1])
if (not isinstance(data, dict) or set(data) != {"successful", "legacy"}
        or any(type(value) is not bool for value in data.values())):
    raise ValueError("Expected successful and legacy booleans")
print(json.dumps({"classification": classify(records(**data))}, sort_keys=True))
