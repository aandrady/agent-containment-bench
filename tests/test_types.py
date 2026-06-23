import json

from harness.types import RunSpec, run_resume_key


def test_resume_key_is_stable_across_run_ids() -> None:
    left = RunSpec(
        framework_id="anthropic_native",
        isolation_id="docker",
        scenario_id="s00_benign",
        model="claude-opus-4-7",
        seed=7,
        max_steps=20,
    )
    right = RunSpec(
        framework_id="anthropic_native",
        isolation_id="docker",
        scenario_id="s00_benign",
        model="claude-opus-4-7",
        seed=7,
        max_steps=20,
    )

    assert left.run_id != right.run_id
    assert left.resume_key() == right.resume_key()


def test_run_resume_key_ignores_result_fields() -> None:
    record = {
        "framework_id": "langchain_react",
        "isolation_id": "gvisor",
        "scenario_id": "s03_fs_traversal",
        "model": "claude-haiku-4-5-20251001",
        "seed": 1,
        "max_steps": 20,
        "temperature": 1.0,
        "run_id": "random",
        "escaped": True,
    }

    key = json.loads(run_resume_key(record))

    assert key == {
        "framework_id": "langchain_react",
        "isolation_id": "gvisor",
        "scenario_id": "s03_fs_traversal",
        "model": "claude-haiku-4-5-20251001",
        "seed": 1,
        "max_steps": 20,
        "temperature": 1.0,
    }
