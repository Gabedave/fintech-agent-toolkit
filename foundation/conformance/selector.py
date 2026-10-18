"""Stdlib synthetic collection adapter; output IDs are independent of the oracle."""
import argparse
import importlib.util
import json
from pathlib import Path
import unittest


def collect(path, keyword=None):
    spec = importlib.util.spec_from_file_location('synthetic_test_store', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    suite = unittest.defaultTestLoader.loadTestsFromModule(module)
    def flatten(node):
        for item in node:
            if isinstance(item, unittest.TestSuite):
                yield from flatten(item)
            else:
                yield item
    ids = ['test_store::' + item._testMethodName for item in flatten(suite)]
    return [name for name in ids if not keyword or keyword in name]


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('path', type=Path)
    parser.add_argument('-k')
    args = parser.parse_args()
    print(json.dumps({'collected_ids': collect(args.path, args.k)}))
