# CI failure states

- `product_failure`: a deterministic source, test, configuration, or contract defect owned by the pull request.
- `test_failure`: the assertion or fixture is wrong, stale, unsafe, or insufficiently isolated.
- `flaky`: the same revision and inputs can pass or fail because of an identified nondeterministic mechanism.
- `infrastructure`: runner, service, network, registry, quota, or GitHub platform failure outside the product behavior.
- `configuration`: workflow permissions, triggers, paths, secrets, matrix, or environment configuration prevents the intended check.
- `superseded`: the result belongs to an older head SHA.
- `unknown`: evidence is insufficient; continue diagnosis rather than guessing.

A retry is evidence about reproducibility, not by itself a classification. Preserve the first failing signal long enough to identify the mechanism.
