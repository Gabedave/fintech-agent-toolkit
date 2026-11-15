"""Final-only native response formatting and the frozen schemas' strict subset.

Only CLI formatting changes: original prompt bases, schemas, semantic scorers
and report/failure rules remain authoritative. The exact effective prompt is
retained for independent review. This helper supplies no expected answers.
"""
import json
import math

KEYWORDS = {'$schema', 'type', 'properties', 'required', 'additionalProperties', 'items', 'enum'}
TYPES = {'object': dict, 'array': list, 'string': str, 'integer': int,
         'boolean': bool, 'null': type(None)}


def validate_schema(schema):
    if not isinstance(schema, dict) or set(schema) - KEYWORDS:
        raise ValueError('unsupported native final schema vocabulary')
    if not isinstance(schema.get('type'), str) or schema['type'] not in {*TYPES, 'number'}:
        raise ValueError('unsupported native final schema type')
    if '$schema' in schema and not isinstance(schema['$schema'], str):
        raise ValueError('$schema must be a string')
    if 'additionalProperties' in schema and type(schema['additionalProperties']) is not bool:
        raise ValueError('additionalProperties must be boolean')
    if 'required' in schema and (not isinstance(schema['required'], list)
            or any(not isinstance(name, str) for name in schema['required'])
            or len(set(schema['required'])) != len(schema['required'])):
        raise ValueError('required must contain unique property names')
    if 'enum' in schema and (not isinstance(schema['enum'], list) or not schema['enum']):
        raise ValueError('enum must be a nonempty array')
    properties = schema.get('properties', {})
    if not isinstance(properties, dict) or any(not isinstance(name, str) for name in properties):
        raise ValueError('properties must be an object')
    for child in properties.values():
        validate_schema(child)
    if 'items' in schema:
        validate_schema(schema['items'])


def final_prompt(original_prompt, schema_text):
    validate_schema(json.loads(schema_text))
    return original_prompt + (
        '\n\nFinal-response transport instructions:\n'
        'Earlier instructions to return only the structured record apply to the final response. '
        'Before the final response, plaintext loading and progress commentary is permitted. '
        'Do not encode progress as a final decision record. The final response must be exactly '
        'one JSON object, without Markdown fences or surrounding prose, conforming to the '
        'unchanged schema below. Schema values specify format, not the correct decision.\n'
        '<final-response-schema>\n' + schema_text + '\n</final-response-schema>\n')


def _same(left, right):
    if type(left) in (int, float) and type(right) in (int, float):
        return ((type(left) is int or math.isfinite(left))
                and (type(right) is int or math.isfinite(right)) and left == right)
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_same(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_same(a, b) for a, b in zip(left, right))
    return left == right


def result_errors(result, schema):
    """Reject invalid shape without coercion; semantic scorers remain separate."""
    validate_schema(schema)
    errors = []
    def visit(value, rule, path):
        kind = rule['type']
        if kind in ('integer', 'number'):
            valid = (type(value) is int or (type(value) is float and math.isfinite(value)
                     and (kind == 'number' or value.is_integer())))
        else:
            valid = type(value) is TYPES[kind]
        if not valid:
            errors.append(f'{path}: expected {kind}')
            return
        if 'enum' in rule and not any(_same(value, choice) for choice in rule['enum']):
            errors.append(f'{path}: value outside enum')
        if kind == 'object':
            properties = rule.get('properties', {})
            for name in rule.get('required', []):
                if name not in value:
                    errors.append(f'{path}.{name}: required property missing')
            for name, child in value.items():
                if name in properties:
                    visit(child, properties[name], f'{path}.{name}')
                elif rule.get('additionalProperties') is False:
                    errors.append(f'{path}.{name}: additional property')
        elif kind == 'array' and 'items' in rule:
            for index, child in enumerate(value):
                visit(child, rule['items'], f'{path}[{index}]')
    visit(result, schema, '$')
    return errors
