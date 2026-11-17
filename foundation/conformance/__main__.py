import sys
from .runner import main, termination_guard

try:
    with termination_guard():
        raise SystemExit(main())
except KeyboardInterrupt:
    print('Observed conformance cancelled; no passing result', file=sys.stderr)
    raise SystemExit(130)
