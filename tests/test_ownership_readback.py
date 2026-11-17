import sqlite3
import tempfile
import unittest
from pathlib import Path

from foundation.conformance.evaluator import load_cases
from foundation.conformance.host import Host, files, initialize


class OwnershipReadbackTests(unittest.TestCase):
    def test_readback_names_actual_store_and_committed_rows(self):
        case = next(c for c in load_cases()['cases'] if c['id'] == '09-ownership-identity')
        variant = next(v for v in case['variants'] if v['id'] == 'compliant-single-authority')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = initialize(root, variant['facts'])
            host = Host(root, state)
            before = host.call('inspect', {'resource': 'ownership'})
            self.assertEqual([], before['committed_ledger_rows'])
            proof = host.call('probe', {'name': 'ownership'})
            self.assertEqual('synthetic.sqlite', proof['storage'])
            self.assertEqual([('op-200', 1250)], proof['ledger'])
            # The JSON resource store is distinct; its emptiness cannot deny
            # the ownership transaction's durable SQLite ledger entry.
            self.assertEqual([], host.call('inspect', {'resource': 'resources'})['ledger'])
            snapshot = files(root)
            readback = host.call('inspect', {'resource': 'ownership'})
            self.assertEqual('synthetic.sqlite', readback['storage'])
            self.assertEqual([('op-200', 'worker-alpha', 12)], readback['rows'])
            self.assertEqual(proof['ledger'], readback['committed_ledger_rows'])
            self.assertEqual(snapshot, files(root))
            with sqlite3.connect(root / 'synthetic.sqlite') as db:
                db.execute('INSERT INTO ledger VALUES (?, ?)', ('later', 50))
            self.assertEqual([('op-200', 1250), ('later', 50)],
                             host.call('inspect', {'resource': 'ownership'})['committed_ledger_rows'])


if __name__ == '__main__':
    unittest.main()
