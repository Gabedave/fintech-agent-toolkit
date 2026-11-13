"""Fixed acceptance identities; v2 is only the owner-approved attachment overlay.

Selection comes from the captured oracle, never from a receipt or candidate flag.
The original v1 bytes, defaults and public compatibility identity remain intact.
"""
import copy
import hashlib
import json
from pathlib import Path

V2_ORACLE_SHA256 = '7917401ab7c89cb0ff23ceda43e6f00e53787802031bd513d2e49862e07c2660'
V2_PUBLIC_ORACLE_SHA256 = 'f40cd7527d67e550be62e1c3a055c9b2723725f331695b51c7561a85aa77a880'
V2_CASES_SHA256 = '5691585484dac5a65d4d7b856bb6d82c9f92b625c2eb38abd965272d1174cf27'
V2_RUBRIC_SHA256 = 'ef0d8af107923d69324519f5b0112db56e4f6212f8e239d27d8b4578858eba69'
V2_FREEZE_SHA256 = '7937545051fd713b12c4f6e54e826fcf100903a1cc7fb488570e86bbf8177a96'
OVERLAY_SHA256 = 'ff72375eadb33345e7407a2a766085a1d55e207cffce7791dac6599c07f04dee'
RUBRIC_SEMANTIC_SHA256 = '1c35fe150b9b6fbbde3a5abf63394e5846f65021f2f0bc34dc3905b9c08da521'


def semantic_sha256(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def version_for_oracle(oracle_sha256):
    from .evaluator import FIXTURE_SHA256, PUBLIC_FIXTURE_SHA256, CASES_SHA256, CONTRACT_SHA256
    from .claim_review import FREEZE_SHA256, RUBRIC_SHA256, PROTOCOL_SHA256
    if oracle_sha256 in (FIXTURE_SHA256, PUBLIC_FIXTURE_SHA256):
        values = (1, FIXTURE_SHA256, PUBLIC_FIXTURE_SHA256, CASES_SHA256, RUBRIC_SHA256, FREEZE_SHA256, 47)
    elif oracle_sha256 in (V2_ORACLE_SHA256, V2_PUBLIC_ORACLE_SHA256):
        values = (2, V2_ORACLE_SHA256, V2_PUBLIC_ORACLE_SHA256, V2_CASES_SHA256, V2_RUBRIC_SHA256, V2_FREEZE_SHA256, 48)
    else:
        raise ValueError('unknown frozen observed oracle')
    result = dict(zip(('version', 'oracle_sha256', 'public_oracle_sha256', 'cases_sha256', 'rubric_sha256', 'freeze_sha256', 'variants'), values))
    result.update(contract_sha256=CONTRACT_SHA256, protocol_sha256=PROTOCOL_SHA256)
    return result


def version_for_binding(binding, suite='observed'):
    if suite != 'observed':
        from .evaluator import PUBLIC_FIXTURE_SHA256
        return version_for_oracle(PUBLIC_FIXTURE_SHA256)
    version = version_for_oracle(binding['oracle_sha256'])
    if (binding['cases_semantic_sha256'] != version['cases_sha256']
            or binding['contract_sha256'] != version['contract_sha256']):
        raise ValueError('observed oracle/semantic/contract binding mismatch')
    return version


def overlay():
    from .claim_review import fixed_file
    return fixed_file('attachment-amendment-v2.json', OVERLAY_SHA256)


def amended_cases(cases):
    from .evaluator import CASES_SHA256
    if semantic_sha256(cases) != CASES_SHA256:
        raise ValueError('amendment requires unchanged v1 cases')
    cases = copy.deepcopy(cases)
    case = next(c for c in cases if c['id'] == '06-review-evidence')
    variants = []
    for variant in case['variants']:
        variants.extend(overlay()['replacement_variants'] if variant['id'] == 'compliant-verified-attachments' else [variant])
    case['variants'] = variants
    if semantic_sha256(cases) != V2_CASES_SHA256:
        raise ValueError('approved amended case semantics changed')
    return cases


def amended_rubric(base):
    change = overlay()
    result = copy.deepcopy(base)
    result.update(change['rubric_fields'])
    for entry in result['entries']:
        if entry['predicate_key'] in change['rubric_applies_to']:
            entry['applies_to'] = change['rubric_applies_to'][entry['predicate_key']]
    result['entries'].extend(change['rubric_added_entries'])
    coverage = []
    for row in result['variant_coverage']:
        coverage.extend(change['rubric_replacement_coverage'] if (row['case_id'], row['variant_id']) == ('06-review-evidence', 'compliant-verified-attachments') else [row])
    result['variant_coverage'] = coverage
    if semantic_sha256(result) != RUBRIC_SEMANTIC_SHA256:
        raise ValueError('approved amended rubric semantics changed')
    return result


def validate_case(case, variant, version):
    """A valid receipt cannot qualify altered caller-supplied expectations."""
    from .evaluator import load_cases
    cases = load_cases()['cases']
    if version['version'] == 2:
        cases = amended_cases(cases)
    expected = next((c for c in cases if c['id'] == case['id']), None)
    if expected != case or variant not in expected['variants']:
        raise ValueError('scored case differs from bound frozen oracle')
