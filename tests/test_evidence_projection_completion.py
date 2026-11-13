import copy
import json
from pathlib import Path
import tempfile
import unittest

from foundation.conformance.claim_review import artifact, report_projection


class EvidenceCompletionTests(unittest.TestCase):
    def project(self, completion):
        started = {'id': 'call', 'type': 'mcp_tool_call', 'server': 'workbench', 'tool': 'host',
                   'arguments': {'action': 'update_evidence', 'fields': {'rendering_check': 'pass', 'access_check': True}}}
        other = copy.deepcopy(started)
        completion(other)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'raw.jsonl').write_text('\n'.join(json.dumps(event) for event in [
                {'type': 'item.started', 'item': started},
                {'type': 'item.completed', 'item': other}]) + '\n')
            return report_projection(root, [artifact(root, 'raw', 'raw_process_stream', 'raw.jsonl')])

    def test_denied_completion_without_arguments_keeps_original_assertions(self):
        def denied(item):
            item.pop('arguments')
            item['error'] = {'message': 'denied'}
        rows = self.project(denied)
        self.assertEqual(['true', 'pass'], [row['text'] for row in rows])
        self.assertEqual([1, 1], [row['source_line'] for row in rows])

    def test_corrected_completion_preserves_original_and_correction(self):
        def corrected(item):
            item['arguments']['fields'] = {'rendering_check': 'pending', 'access_check': False}
        rows = self.project(corrected)
        self.assertEqual(['true', 'pass', 'false', 'pending'], [row['text'] for row in rows])
        self.assertEqual([1, 1, 2, 2], [row['source_line'] for row in rows])

    def test_exact_completion_deduplicates_equivalent_decoded_arguments(self):
        rows = self.project(lambda item: item.update(arguments=json.dumps(item['arguments'])))
        self.assertEqual(['true', 'pass'], [row['text'] for row in rows])
        self.assertEqual([2, 2], [row['source_line'] for row in rows])

    def test_other_server_cannot_erase_first_assertion(self):
        rows = self.project(lambda item: item.update(server='other'))
        self.assertEqual([1, 1, 2, 2], [row['source_line'] for row in rows])


if __name__ == '__main__':
    unittest.main()
