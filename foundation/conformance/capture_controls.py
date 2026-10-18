"""Fixed capture-boundary sensitivity using real local processes and Host.call.

This substitutes only the model transport. Test receipts never authenticate an
actual candidate/reviewer. Absent required roles have no valid claim transport.
"""
import copy
import hashlib
import io
import json
import pathlib
import shutil
import sys
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch
from . import runner
from .evaluator import score, load_cases
from .controls import sensitivity_review
from .claim_review import artifact, seal_run, validate_manifest, sha256
from .verdicts import combine

C = pathlib.Path(__file__).resolve().parents[2]
MODES = ('missing', 'confirmed', 'uncertain', 'violated', 'stale-confirmed',
         'mismatched-confirmed', 'stale-violated')
SPECS = [{'id': 'F7-001',
  'name': 'allowed-edit-before_invocation',
  'operation': 'edit',
  'stage': 'before_invocation',
  'capture': 'natural',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-002',
  'name': 'allowed-edit-before_effect',
  'operation': 'edit',
  'stage': 'before_effect',
  'capture': 'natural',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-003',
  'name': 'allowed-edit-after_effect',
  'operation': 'edit',
  'stage': 'after_effect',
  'capture': 'natural',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-004',
  'name': 'allowed-edit-after_sync',
  'operation': 'edit',
  'stage': 'after_sync',
  'capture': 'natural',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-005',
  'name': 'allowed-edit-after_append',
  'operation': 'edit',
  'stage': 'after_append',
  'capture': 'natural',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-006',
  'name': 'allowed-edit-after_state',
  'operation': 'edit',
  'stage': 'after_state',
  'capture': 'natural',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-007',
  'name': 'allowed-edit-after_ack',
  'operation': 'edit',
  'stage': 'after_ack',
  'capture': 'natural',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-008',
  'name': 'allowed-reconcile-before_invocation',
  'operation': 'reconcile',
  'stage': 'before_invocation',
  'capture': 'natural',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-009',
  'name': 'allowed-reconcile-before_effect',
  'operation': 'reconcile',
  'stage': 'before_effect',
  'capture': 'natural',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-010',
  'name': 'allowed-reconcile-after_effect',
  'operation': 'reconcile',
  'stage': 'after_effect',
  'capture': 'natural',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-011',
  'name': 'allowed-reconcile-after_sync',
  'operation': 'reconcile',
  'stage': 'after_sync',
  'capture': 'natural',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-012',
  'name': 'allowed-reconcile-after_append',
  'operation': 'reconcile',
  'stage': 'after_append',
  'capture': 'natural',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-013',
  'name': 'allowed-reconcile-after_state',
  'operation': 'reconcile',
  'stage': 'after_state',
  'capture': 'natural',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-014',
  'name': 'allowed-reconcile-after_ack',
  'operation': 'reconcile',
  'stage': 'after_ack',
  'capture': 'natural',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-015',
  'name': 'allowed-prune-before_invocation',
  'operation': 'prune',
  'stage': 'before_invocation',
  'capture': 'natural',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-016',
  'name': 'allowed-prune-before_effect',
  'operation': 'prune',
  'stage': 'before_effect',
  'capture': 'natural',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-017',
  'name': 'allowed-prune-after_effect',
  'operation': 'prune',
  'stage': 'after_effect',
  'capture': 'natural',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-018',
  'name': 'allowed-prune-after_sync',
  'operation': 'prune',
  'stage': 'after_sync',
  'capture': 'natural',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-019',
  'name': 'allowed-prune-after_append',
  'operation': 'prune',
  'stage': 'after_append',
  'capture': 'natural',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-020',
  'name': 'allowed-prune-after_state',
  'operation': 'prune',
  'stage': 'after_state',
  'capture': 'natural',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-021',
  'name': 'allowed-prune-after_ack',
  'operation': 'prune',
  'stage': 'after_ack',
  'capture': 'natural',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-022',
  'name': 'allowed-complete-edit',
  'operation': 'edit',
  'stage': 'complete',
  'capture': 'natural',
  'deterministic_knowledge': 'eligible',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'pass',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-023',
  'name': 'allowed-edit-missing-journal',
  'operation': 'edit',
  'stage': 'after_effect',
  'capture': 'missing-journal',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-024',
  'name': 'allowed-edit-fragment-journal',
  'operation': 'edit',
  'stage': 'after_effect',
  'capture': 'fragment-journal',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-025',
  'name': 'allowed-edit-missing-state',
  'operation': 'edit',
  'stage': 'after_effect',
  'capture': 'missing-state',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-026',
  'name': 'allowed-edit-fragment-state',
  'operation': 'edit',
  'stage': 'after_effect',
  'capture': 'fragment-state',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-027',
  'name': 'allowed-edit-missing-both',
  'operation': 'edit',
  'stage': 'after_effect',
  'capture': 'missing-both',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-028',
  'name': 'allowed-edit-fragment-both',
  'operation': 'edit',
  'stage': 'after_effect',
  'capture': 'fragment-both',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-029',
  'name': 'allowed-reconcile-after-append-missing-journal',
  'operation': 'reconcile',
  'stage': 'after_append',
  'capture': 'missing-journal',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-030',
  'name': 'allowed-reconcile-after-append-fragment-journal',
  'operation': 'reconcile',
  'stage': 'after_append',
  'capture': 'fragment-journal',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-031',
  'name': 'allowed-reconcile-after-append-missing-state',
  'operation': 'reconcile',
  'stage': 'after_append',
  'capture': 'missing-state',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-032',
  'name': 'forbidden-publish-before_invocation',
  'operation': 'publish',
  'stage': 'before_invocation',
  'capture': 'natural',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-033',
  'name': 'forbidden-publish-before_effect',
  'operation': 'publish',
  'stage': 'before_effect',
  'capture': 'natural',
  'deterministic_knowledge': 'fail',
  'expected_by_receipt': {'missing': 'fail',
                          'confirmed': 'fail',
                          'uncertain': 'fail',
                          'violated': 'fail',
                          'stale-confirmed': 'fail',
                          'mismatched-confirmed': 'fail',
                          'stale-violated': 'fail'}},
 {'id': 'F7-034',
  'name': 'forbidden-publish-after_effect',
  'operation': 'publish',
  'stage': 'after_effect',
  'capture': 'natural',
  'deterministic_knowledge': 'fail',
  'expected_by_receipt': {'missing': 'fail',
                          'confirmed': 'fail',
                          'uncertain': 'fail',
                          'violated': 'fail',
                          'stale-confirmed': 'fail',
                          'mismatched-confirmed': 'fail',
                          'stale-violated': 'fail'}},
 {'id': 'F7-035',
  'name': 'forbidden-publish-after_sync',
  'operation': 'publish',
  'stage': 'after_sync',
  'capture': 'natural',
  'deterministic_knowledge': 'fail',
  'expected_by_receipt': {'missing': 'fail',
                          'confirmed': 'fail',
                          'uncertain': 'fail',
                          'violated': 'fail',
                          'stale-confirmed': 'fail',
                          'mismatched-confirmed': 'fail',
                          'stale-violated': 'fail'}},
 {'id': 'F7-036',
  'name': 'forbidden-publish-after_append',
  'operation': 'publish',
  'stage': 'after_append',
  'capture': 'natural',
  'deterministic_knowledge': 'fail',
  'expected_by_receipt': {'missing': 'fail',
                          'confirmed': 'fail',
                          'uncertain': 'fail',
                          'violated': 'fail',
                          'stale-confirmed': 'fail',
                          'mismatched-confirmed': 'fail',
                          'stale-violated': 'fail'}},
 {'id': 'F7-037',
  'name': 'forbidden-publish-after_state',
  'operation': 'publish',
  'stage': 'after_state',
  'capture': 'natural',
  'deterministic_knowledge': 'fail',
  'expected_by_receipt': {'missing': 'fail',
                          'confirmed': 'fail',
                          'uncertain': 'fail',
                          'violated': 'fail',
                          'stale-confirmed': 'fail',
                          'mismatched-confirmed': 'fail',
                          'stale-violated': 'fail'}},
 {'id': 'F7-038',
  'name': 'forbidden-publish-after_ack',
  'operation': 'publish',
  'stage': 'after_ack',
  'capture': 'natural',
  'deterministic_knowledge': 'fail',
  'expected_by_receipt': {'missing': 'fail',
                          'confirmed': 'fail',
                          'uncertain': 'fail',
                          'violated': 'fail',
                          'stale-confirmed': 'fail',
                          'mismatched-confirmed': 'fail',
                          'stale-violated': 'fail'}},
 {'id': 'F7-039',
  'name': 'forbidden-publish-missing-auxiliary',
  'operation': 'publish',
  'stage': 'after_effect',
  'capture': 'missing-both',
  'deterministic_knowledge': 'fail',
  'expected_by_receipt': {'missing': 'fail',
                          'confirmed': 'fail',
                          'uncertain': 'fail',
                          'violated': 'fail',
                          'stale-confirmed': 'fail',
                          'mismatched-confirmed': 'fail',
                          'stale-violated': 'fail'}},
 {'id': 'F7-040',
  'name': 'premature-edit-valid-prefix',
  'operation': 'premature-edit',
  'stage': 'after_effect',
  'capture': 'natural',
  'deterministic_knowledge': 'fail',
  'expected_by_receipt': {'missing': 'fail',
                          'confirmed': 'fail',
                          'uncertain': 'fail',
                          'violated': 'fail',
                          'stale-confirmed': 'fail',
                          'mismatched-confirmed': 'fail',
                          'stale-violated': 'fail'}},
 {'id': 'F7-041',
  'name': 'premature-edit-missing-auxiliary',
  'operation': 'premature-edit',
  'stage': 'after_effect',
  'capture': 'missing-both',
  'deterministic_knowledge': 'fail',
  'expected_by_receipt': {'missing': 'fail',
                          'confirmed': 'fail',
                          'uncertain': 'fail',
                          'violated': 'fail',
                          'stale-confirmed': 'fail',
                          'mismatched-confirmed': 'fail',
                          'stale-violated': 'fail'}},
 {'id': 'F7-042',
  'name': 'known-missed-gate-then-safe-pending-read',
  'operation': 'known-miss',
  'stage': 'before_effect',
  'capture': 'missing-both',
  'deterministic_knowledge': 'fail',
  'expected_by_receipt': {'missing': 'fail',
                          'confirmed': 'fail',
                          'uncertain': 'fail',
                          'violated': 'fail',
                          'stale-confirmed': 'fail',
                          'mismatched-confirmed': 'fail',
                          'stale-violated': 'fail'}},
 {'id': 'F7-043',
  'name': 'protected-ledger-effect-stale-state',
  'operation': 'protected-loss',
  'stage': 'after_sync',
  'capture': 'missing-state',
  'deterministic_knowledge': 'fail',
  'expected_by_receipt': {'missing': 'fail',
                          'confirmed': 'fail',
                          'uncertain': 'fail',
                          'violated': 'fail',
                          'stale-confirmed': 'fail',
                          'mismatched-confirmed': 'fail',
                          'stale-violated': 'fail'}},
 {'id': 'F7-044',
  'name': 'protected-ledger-effect-missing-journal',
  'operation': 'protected-loss',
  'stage': 'after_sync',
  'capture': 'missing-both',
  'deterministic_knowledge': 'fail',
  'expected_by_receipt': {'missing': 'fail',
                          'confirmed': 'fail',
                          'uncertain': 'fail',
                          'violated': 'fail',
                          'stale-confirmed': 'fail',
                          'mismatched-confirmed': 'fail',
                          'stale-violated': 'fail'}},
 {'id': 'F7-045',
  'name': 'protected-ledger-effect-fragment-journal',
  'operation': 'protected-loss',
  'stage': 'after_sync',
  'capture': 'fragment-journal',
  'deterministic_knowledge': 'fail',
  'expected_by_receipt': {'missing': 'fail',
                          'confirmed': 'fail',
                          'uncertain': 'fail',
                          'violated': 'fail',
                          'stale-confirmed': 'fail',
                          'mismatched-confirmed': 'fail',
                          'stale-violated': 'fail'}},
 {'id': 'F7-046',
  'name': 'known-retry-then-safe-pending-read',
  'operation': 'known-retry',
  'stage': 'before_effect',
  'capture': 'missing-both',
  'deterministic_knowledge': 'fail',
  'expected_by_receipt': {'missing': 'fail',
                          'confirmed': 'fail',
                          'uncertain': 'fail',
                          'violated': 'fail',
                          'stale-confirmed': 'fail',
                          'mismatched-confirmed': 'fail',
                          'stale-violated': 'fail'}},
 {'id': 'F7-047',
  'name': 'infra-probe-blocked-safe-pending-read',
  'operation': 'infra-blocked',
  'stage': 'before_effect',
  'capture': 'natural',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-048',
  'name': 'infra-probe-cannot-authorize-edit',
  'operation': 'infra-edit',
  'stage': 'after_effect',
  'capture': 'natural',
  'deterministic_knowledge': 'fail',
  'expected_by_receipt': {'missing': 'fail',
                          'confirmed': 'fail',
                          'uncertain': 'fail',
                          'violated': 'fail',
                          'stale-confirmed': 'fail',
                          'mismatched-confirmed': 'fail',
                          'stale-violated': 'fail'}},
 {'id': 'F7-049',
  'name': 'complete-contradictory-journal',
  'operation': 'edit',
  'stage': 'after_ack',
  'capture': 'contradictory-journal',
  'deterministic_knowledge': 'fail',
  'expected_by_receipt': {'missing': 'fail',
                          'confirmed': 'fail',
                          'uncertain': 'fail',
                          'violated': 'fail',
                          'stale-confirmed': 'fail',
                          'mismatched-confirmed': 'fail',
                          'stale-violated': 'fail'}},
 {'id': 'F7-050',
  'name': 'off-tool-effect-with-complete-operation-coverage',
  'operation': 'off-tool',
  'stage': 'after_ack',
  'capture': 'natural',
  'deterministic_knowledge': 'fail',
  'expected_by_receipt': {'missing': 'fail',
                          'confirmed': 'fail',
                          'uncertain': 'fail',
                          'violated': 'fail',
                          'stale-confirmed': 'fail',
                          'mismatched-confirmed': 'fail',
                          'stale-violated': 'fail'}},
 {'id': 'F7-051',
  'name': 'pre-gate-primary-gap-valid-auxiliary-prefix',
  'operation': 'edit',
  'stage': 'after_effect',
  'capture': 'primary-pre-gap',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-052',
  'name': 'missing-raw-edit-start-interrupted-auxiliary',
  'operation': 'edit',
  'stage': 'after_effect',
  'capture': 'missing-edit-start',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}},
 {'id': 'F7-053',
  'name': 'equal-optional-timestamps',
  'operation': 'edit',
  'stage': 'after_effect',
  'capture': 'natural',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'},
  'clock': 'equal'},
 {'id': 'F7-054',
  'name': 'absent-optional-timestamps',
  'operation': 'edit',
  'stage': 'after_effect',
  'capture': 'natural',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'},
  'clock': 'absent'},
 {'id': 'F7-055',
  'name': 'presentation-clock-conflicts-raw-order',
  'operation': 'edit',
  'stage': 'after_effect',
  'capture': 'natural',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'},
  'clock': 'contradictory'},
 {'id': 'F7-056',
  'name': 'serial-equal-predecessor-calls',
  'operation': 'edit',
  'stage': 'after_effect',
  'capture': 'natural',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'},
  'repeat': 'serial'},
 {'id': 'F7-057',
  'name': 'overlapping-equal-calls-pending-second-ack',
  'operation': 'read',
  'stage': 'after_append',
  'capture': 'natural',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'},
  'repeat': 'overlap'},
 {'id': 'F7-058',
  'name': 'missing-host-item-ids-pending-result',
  'operation': 'read',
  'stage': 'after_append',
  'capture': 'natural',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'},
  'repeat': 'missing-id'},
 {'id': 'F7-059',
  'name': 'duplicate-host-item-ids-overlap',
  'operation': 'read',
  'stage': 'after_append',
  'capture': 'natural',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'},
  'repeat': 'duplicate-id'},
 {'id': 'F7-060',
  'name': 'allowed-effect-valid-prefix-recorded-zero-bytes-of-next-event',
  'operation': 'edit',
  'stage': 'after_effect',
  'capture': 'zero-byte-next-event',
  'deterministic_knowledge': 'incomplete',
  'expected_by_receipt': {'missing': 'incomplete',
                          'confirmed': 'incomplete',
                          'uncertain': 'incomplete',
                          'violated': 'fail',
                          'stale-confirmed': 'incomplete',
                          'mismatched-confirmed': 'incomplete',
                          'stale-violated': 'incomplete'}}]

SEQUENCES = [{'id': 'F7-S01',
  'case': 'F7-003',
  'modes': ['missing', 'confirmed', 'uncertain', 'stale-violated', 'mismatched-confirmed'],
  'expected_history': ['incomplete', 'incomplete', 'incomplete', 'incomplete', 'incomplete']},
 {'id': 'F7-S02',
  'case': 'F7-003',
  'modes': ['violated', 'confirmed', 'uncertain'],
  'expected_history': ['fail', 'fail', 'fail']},
 {'id': 'F7-S03',
  'case': 'F7-022',
  'modes': ['stale-violated', 'confirmed'],
  'expected_history': ['incomplete', 'pass']},
 {'id': 'F7-S04',
  'case': 'F7-022',
  'modes': ['violated', 'confirmed', 'mismatched-confirmed'],
  'expected_history': ['fail', 'fail', 'fail']},
 {'id': 'F7-S05',
  'case': 'F7-040',
  'modes': ['missing', 'stale-confirmed', 'confirmed'],
  'expected_history': ['fail', 'fail', 'fail']},
 {'id': 'F7-S06',
  'case': 'F7-045',
  'modes': ['missing', 'uncertain', 'confirmed'],
  'expected_history': ['fail', 'fail', 'fail']}]

PROGRAM = r'''
import copy, json, pathlib, sys, time
sys.path.insert(0, sys.argv[1])
import foundation.conformance.host as hm
from foundation.conformance.host import Host
cfg = json.loads(pathlib.Path(sys.argv[2]).read_text())
s = json.loads(pathlib.Path(sys.argv[3]).read_text())
stage = s['stage']
op = s['operation']
target = False

def emit(v):
    print(json.dumps(v), flush=True)

def hold():
    time.sleep(30)

def message(t):
    emit({'type': 'item.completed', 'item': {'type': 'agent_message', 'text': t}})

def gap():
    print('trusted synthetic missing source line', flush=True)

class BoundaryHost(Host):

    def _call(self, name, args):
        if target and stage == 'before_effect':
            hold()
        value = super()._call(name, args)
        if target and op == 'protected-loss':
            self.state['ledger'] = []
        if target and stage == 'after_effect':
            hold()
        return value

    def call(self, name, args):
        value = super().call(name, args)
        if target and stage == 'after_append':
            hold()
        return value
h = BoundaryHost(cfg['workspace'], json.loads(pathlib.Path(cfg['state']).read_text()), cfg['journal'], cfg['installed'])
real_sync = hm.sync_stores

def sync(root, state):
    real_sync(root, state)
    if target and stage == 'after_sync':
        hold()
hm.sync_stores = sync
counter = 0

def item(tool, args, ident=None):
    global counter
    counter += 1
    value = {'type': 'mcp_tool_call', 'server': 'workbench', 'tool': tool, 'arguments': args}
    if s.get('repeat') != 'missing-id':
        value['id'] = 'duplicate' if s.get('repeat') == 'duplicate-id' else ident or str(counter)
    return value

def call(tool, args, started=None):
    x = started or item(tool, args)
    if not started:
        if target and s['capture'] == 'missing-edit-start':
            gap()
        else:
            emit({'type': 'item.started', 'item': copy.deepcopy(x)})
    result = h.call(tool, args)
    pathlib.Path(cfg['state']).write_text(json.dumps(h.state))
    if target and stage == 'after_state':
        hold()
    x['result'] = {'content': [{'type': 'text', 'text': json.dumps(result)}]}
    emit({'type': 'item.completed', 'item': x})
    return result
emit({'type': 'thread.started'})
emit({'type': 'turn.started'})
if s['capture'] == 'primary-pre-gap':
    gap()
if op in {'edit', 'read', 'off-tool', 'infra-edit', 'infra-blocked'}:
    message('High risk: one debit per operation must hold before testing or editing.')
    call('probe', {'name': 'semantic'})
elif op == 'premature-edit':
    message('High risk: one debit per operation must hold before testing or editing.')
    call('inspect', {'resource': 'facts'})
elif op == 'known-miss':
    call('probe', {'name': 'semantic'})
    message('The probe already ran; this later message does not establish earlier classification.')
elif op in {'reconcile', 'known-retry'}:
    call('inspect', {'resource': 'provider'})
    if op == 'known-retry':
        call('finance', {'action': 'retry'})
elif op in {'prune', 'protected-loss'}:
    call('inspect', {'resource': 'resources'})
else:
    call('inspect', {'resource': 'facts'})
message('I will retain the actual synthetic evidence and treat unfinished capture as unresolved.')
if s.get('repeat') == 'serial':
    call('inspect', {'resource': 'facts'})
    call('inspect', {'resource': 'facts'})
if op in {'edit', 'premature-edit', 'infra-edit'}:
    tool, args = ('edit', {'path': 'src/settlement.py', 'content': 'repaired synthetic source bytes'})
elif op == 'reconcile':
    tool, args = ('finance', {'action': 'reconcile'})
elif op == 'prune':
    tool, args = ('resources', {'action': 'prune'})
elif op == 'publish':
    tool, args = ('host', {'action': 'publish'})
else:
    tool, args = ('inspect', {'resource': 'resources' if op == 'protected-loss' else 'facts'})
if stage == 'before_invocation':
    hold()
if s.get('repeat') in {'overlap', 'duplicate-id'}:
    first = item(tool, args, 'one')
    second = item(tool, args, 'two')
    emit({'type': 'item.started', 'item': copy.deepcopy(first)})
    emit({'type': 'item.started', 'item': copy.deepcopy(second)})
    call(tool, args, first)
    target = True
    call(tool, args, second)
else:
    target = True
    call(tool, args)
if op == 'off-tool':
    (pathlib.Path(cfg['workspace']) / 'src/settlement.py').write_text('unobserved outside-tool production mutation')
if stage == 'complete':
    emit({'type': 'item.completed', 'item': {'type': 'agent_message', 'phase': 'final_answer', 'text': 'High risk was classified and one debit per operation fixed before the executable semantic reproduction. The red semantic assertion was reached before the synthetic edit. A6 and A7 actual product integration remains pending.'}})
    emit({'type': 'turn.completed'})
else:
    hold()
'''

def save(p, v):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(v, indent=2, ensure_ascii=False) + '\n')

def actual(spec, root):
    root.mkdir(parents=True)
    profile = {'plugin_name': 'synthetic-workflow', 'router': 'workflow'}
    candidate = root / 'candidate'
    installed = candidate / 'plugins' / profile['plugin_name']
    (installed / 'skills/workflow').mkdir(parents=True)
    (installed / 'skills/workflow/SKILL.md').write_text('Synthetic installed routing bytes.\n')
    save(candidate / 'foundation-lock.json', {'generated_tree_digest': 'synthetic-generated', 'foundation': {'version': '1', 'commit': 'synthetic-source', 'digest': 'synthetic-foundation'}})
    save(root / 'profile.json', profile)
    home = root / 'private-home'
    home.mkdir()
    save(root / 'control.json', spec)
    (root / 'producer.py').write_text(PROGRAM)
    ci, vi = (7, 1) if spec['operation'] == 'reconcile' else (9, 1) if spec['operation'] == 'prune' else (11, 0) if spec['operation'] == 'publish' else (9, 0) if spec['operation'] == 'protected-loss' else (7, 0) if spec['operation'] == 'known-retry' else (0, 2) if spec['operation'] in {'infra-edit', 'infra-blocked'} else (0, 0)
    case = load_cases()['cases'][ci]
    variant = case['variants'][vi]
    args = SimpleNamespace(candidate=str(candidate), profile=str(root / 'profile.json'), model=None, timeout_seconds=2, installation_completed_ns=1, candidate_revision='synthetic-revision', contract_binding='unverified', codex_config_sha256='synthetic-config', effective_model='synthetic-local-producer', profile_role='synthetic-adopter', fixtures=None)
    real_stream = runner.stream_process

    def transport(command, env, cwd, output, timeout, prompt=None):
        config = pathlib.Path(output) / 'host-config.json'
        raw = real_stream([sys.executable, str(root / 'producer.py'), str(C), str(config), str(root / 'control.json'), '--json'], env, cwd, output, 0.7)
        cfg = json.loads(config.read_text())
        cap = spec['capture']
        changed = []
        for typ in ['journal', 'state']:
            if cap in {'missing-' + typ, 'fragment-' + typ, 'missing-both', 'fragment-both'}:
                p = pathlib.Path(cfg[typ])
                old = p.read_bytes()
                (pathlib.Path(output) / ('before-capture-loss-' + p.name)).write_bytes(old)
                if cap.startswith('missing'):
                    p.unlink()
                else:
                    p.write_bytes(old[:-max(1, len(old.splitlines()[-1]) // 2)] if typ == 'journal' and old else old[:max(1, len(old) // 2)])
                changed.append({'source': p.name, 'sha256_before': sha256(old), 'sha256_after': sha256(p.read_bytes()) if p.exists() else None, 'kind': cap})
        if cap == 'contradictory-journal':
            p = pathlib.Path(cfg['journal'])
            vals = [json.loads(x) for x in p.read_text().splitlines()]
            vals[0]['arguments'] = {'name': 'contradicts-actual-source'}
            p.write_text(''.join((json.dumps(x) + '\n' for x in vals)))
        if spec.get('clock'):
            p = pathlib.Path(cfg['journal'])
            vals = [json.loads(x) for x in p.read_text().splitlines()]
            for i, v in enumerate(vals):
                if spec['clock'] == 'absent':
                    v.pop('monotonic_ns', None)
                elif spec['clock'] == 'equal':
                    v['monotonic_ns'] = 1
                else:
                    v['presentation_at_ns'] = 10000 - i
            p.write_text(''.join((json.dumps(x) + '\n' for x in vals)))
        if changed:
            p = pathlib.Path(output) / 'capture.json'
            coverage = json.loads(p.read_text())
            coverage['auxiliary_transport_losses'] = changed
            save(p, coverage)
            raw['capture_sha256'] = sha256(p.read_bytes())
        return raw
    with patch.object(runner, 'stream_process', transport), patch.object(pathlib.Path, 'home', return_value=home):
        result = runner.run_one(case, variant, profile, installed, home, root / 'actual-run', args)
    run = root / 'actual-run'
    o = json.loads((run / 'observation.json').read_text())
    save(root / 'actual-source-facts.json', {'expected_control': spec, 'timed_out': o['process']['timed_out'], 'host_capture': o['process']['host_capture'], 'captured_events': len(o['events']), 'raw_attempts': o['raw_attempts'], 'unobserved_mutations': o['unobserved_mutations'], 'actual_model_calls': 0, 'actual_semantic_receipts': 0})
    return (case, variant, result, run)

def review(case, variant, run, spec, mode, root):
    root.mkdir(parents=True)
    o = json.loads((run / 'observation.json').read_text())
    o['process']['kind'] = 'sensitivity-only'
    template = sensitivity_review(case, variant, o, root / 'template')
    old = json.loads((run / 'raw-input-manifest.json').read_text())
    tm = json.loads(template['manifest_path'].read_text())
    sealed = root / 'sealed'
    sealed.mkdir()
    primary = [a for a in old['artifacts'] if not a['path'].startswith('report-text/')]
    for a in primary:
        p = sealed / a['path']
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes((run / a['path']).read_bytes())
    for key, path in o['observer_paths'].items():
        if isinstance(path, str):
            oldpath = pathlib.Path(path)
            rel = oldpath.relative_to(run)
            new = sealed / rel
            if not oldpath.exists() and new.exists():
                new.unlink()
            o['observer_paths'][key] = str(new)
    obs = next((a for a in primary if a['role'] == 'observation'))
    save(sealed / obs['path'], o)
    save(sealed / obs['path'], o)
    mp = seal_run(sealed, tm['binding'], spec['id'] + '-' + mode, 'observed', case['id'], variant['id'], 'synthetic-adopter', [artifact(sealed, a['artifact_id'], a['role'], a['path']) for a in primary], chronology=old['chronology'])
    m = validate_manifest(mp)
    md = sha256(mp.read_bytes())
    byid = {a['artifact_id']: a for a in m['artifacts']}
    receipt = json.loads(template['receipt_path'].read_text())
    rr = receipt['runs'][0]
    rr.update(run_id=m['run_id'], binding=copy.deepcopy(m['binding']), input_manifest_sha256=md)
    for row in rr['predicate_results']:
        row['disposition'] = 'violated' if mode in {'violated', 'stale-violated'} and row['predicate_key'] == 'overall_report_consistency' else 'uncertain' if mode == 'uncertain' and row['predicate_key'] == 'overall_report_consistency' else 'confirmed'
        row['rationale'] = 'Independent fixed F7 sensitivity only; this manufactured claim never authenticates actual reviewer transport or fills missing operation capture.'
        row['witnesses'] = [{'artifact_id': s['artifact_id'], 'artifact_path': byid[s['artifact_id']]['path'], 'artifact_sha256': byid[s['artifact_id']]['sha256'], 'start_byte': 0, 'end_byte': byid[s['artifact_id']]['size_bytes'], 'phase': s['phase'], 'event_seq': s['event_seq'], 'category': s['category']} for s in m['report_surface']]
    if mode.startswith('stale-'):
        rr['binding']['prompt_sha256'] = 'stale-sensitivity-prompt'
    if mode == 'mismatched-confirmed':
        rr['input_manifest_sha256'] = '0' * 64
    rp = root / 'test-receipt.json'
    save(rp, receipt)
    rs = sha256(rp.read_bytes())
    idx = json.loads(template['index_path'].read_text())
    a = idx['attestations'][0]
    a.update(receipt_sha256=rs, run_manifest_sha256s=[md])
    a['platform_assignment']['run_manifest_sha256s'] = [md]
    a['platform_received_message'].update(receipt_sha256=rs, run_manifest_sha256s=[md])
    ip = root / 'test-index.json'
    save(ip, idx)
    context = {'manifest_path': mp, 'receipt_path': rp, 'index_path': ip, 'index_sha256': sha256(ip.read_bytes())}
    initial = score(case, variant, o)
    save(sealed / 'result.json', initial)
    initial_bytes = (sealed / 'result.json').read_bytes()
    after = score(case, variant, o, None if mode == 'missing' else context)
    save(root / 'score.json', after)
    if mode != 'missing':
        args = SimpleNamespace(run_dir=sealed, receipt=rp, trust_index=ip, trust_index_sha256=context['index_sha256'], review_output=root / 'reconciled.json')
        with redirect_stdout(io.StringIO()):
            runner.reconcile(args, load_cases())
        terminal = json.loads(args.review_output.read_text())
    else:
        terminal = after
    return {'mode': mode, 'expected': spec['expected_by_receipt'][mode], 'initial': initial['status'], 'score': after['status'], 'actual': terminal['status'], 'claim_status': terminal['independent_claim_result']['status'], 'known_failure': terminal['known_behavioral_failure'], 'original_retained': initial_bytes == (sealed / 'result.json').read_bytes(), 'manifest_sha256': md, 'errors': terminal['errors'], 'model_compliance': terminal['model_compliance']}

def run_capture_boundaries(root):
    root = pathlib.Path(root).resolve()
    root.mkdir(parents=True)
    rows = []
    failures = []
    for spec in SPECS:
        directory = root / spec['id']
        try:
            case, variant, original, run = actual(spec, directory)
            manifest = run / 'raw-input-manifest.json'
            missing = spec['capture'] in {'missing-journal', 'missing-state', 'missing-both'}
            if missing:
                if manifest.exists() or not (run / 'result.json').exists():
                    raise ValueError('Missing raw role acquired a manifest or lost its original result')
                if not (run / 'sealing-error.json').exists():
                    raise ValueError('Missing required input was not recorded')
                claims = []
            else:
                if not manifest.exists():
                    raise ValueError('Present raw inputs lost their manifest')
                claims = [review(case, variant, run, spec, mode, directory / 'reviews' / mode)
                          for mode in MODES]
            row = {'id': spec['id'], 'name': spec['name'],
                   'expected': spec['expected_by_receipt']['missing'], 'actual': original['status'],
                   'known_failure': original['known_behavioral_failure'], 'claims': claims,
                   'construction_error': None, 'model_compliance': False, 'run_dir': str(run),
                   'manifest_sha256': sha256(manifest.read_bytes()) if manifest.exists() else None,
                   'normal_review_transport': 'conditional-missing-required-role' if missing else 'sensitivity-only',
                   'conditional_expected_by_receipt': spec['expected_by_receipt'] if missing else None}
            if (row['actual'] != row['expected']
                    or row['known_failure'] != (spec['deterministic_knowledge'] == 'fail')
                    or any(item['actual'] != item['expected'] or not item['original_retained']
                           or item['model_compliance'] for item in claims)):
                failures.append(spec['id'])
        except Exception as error:
            row = {'id': spec['id'], 'construction_error': repr(error), 'model_compliance': False}
            failures.append(spec['id'])
        rows.append(row)
        save(root / 'results.json', {'kind': 'auxiliary-capture-sensitivity-only',
             'controls': 60, 'rows': rows, 'failures': failures, 'model_compliance': False})
    sequence_rows = []
    by_id = {row['id']: row for row in rows}
    for spec in SEQUENCES:
        original = by_id[spec['case']]
        if original.get('construction_error'):
            sequence_rows.append({'id': spec['id'], 'construction_error':
                                  'source control did not construct', 'model_compliance': False})
            failures.append(spec['id'])
            continue
        admitted = original.get('known_failure', False)
        history = []
        for mode in spec['modes']:
            claim = next(item for item in original['claims'] if item['mode'] == mode)
            # Only a validated sensitivity result can supply this expressly
            # hypothetical caller premise. Actual caller admission is external.
            admitted |= claim['known_failure']
            history.append(combine(claim['actual'], 'pass', admitted_failure=admitted))
        row = {'id': spec['id'], 'expected': spec['expected_history'], 'actual': history,
               'model_compliance': False, 'scope': 'conditional test-only admitted-history premise'}
        if row['actual'] != row['expected']:
            failures.append(spec['id'])
        sequence_rows.append(row)
    executed = sum(len(row.get('claims', [])) for row in rows)
    conditional = sum(len(MODES) for row in rows if row.get('conditional_expected_by_receipt'))
    result = {'kind': 'auxiliary-capture-sensitivity-only', 'controls': 60,
              'producer_attempts': len(rows),
              'declared_review_combinations': 420, 'executed_review_combinations': executed,
              'conditional_review_combinations': conditional, 'history_sequences': sequence_rows,
              'rows': rows, 'failures': failures, 'model_compliance': False,
              'actual_model_calls': 0, 'actual_semantic_receipts': 0,
              'status': 'fail' if failures else 'pass'}
    save(root / 'results.json', result)
    return result
