"""The golden file the TypeScript engine is checked against must be current.

If this fails, regenerate it with `python tests/conformance.py` and then make
`npm test` pass in frontend/ — see conformance.py.
"""
import conformance


def test_golden_file_is_current():
    assert conformance.GOLDEN.exists(), "run: python tests/conformance.py"
    assert conformance.GOLDEN.read_text() == conformance.render(), (
        "frontend/src/engine/conformance.json is stale: run python tests/conformance.py, "
        "then make the TypeScript port pass"
    )
