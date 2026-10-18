import json
import sys
from flow import run
from support import Queue


if len(sys.argv) != 2:
    raise ValueError("Expected exactly one JSON argument")
data = json.loads(sys.argv[1])
if (not isinstance(data, dict) or set(data) != {"completed", "incoming", "waiting"}
        or any(not isinstance(value, list) or len(value) > 8 for value in data.values())
        or any(type(item) is not int for value in data.values() for item in value)
        or len(set(item for value in data.values() for item in value)) !=
        sum(len(value) for value in data.values())):
    raise ValueError("Expected distinct integer IDs in completed, incoming, and waiting arrays")
queue = Queue(**data)
result = run(queue)
print(json.dumps({"completed": queue.completed, "incoming": queue.incoming,
                  "waiting": queue.waiting, **result}, sort_keys=True))
