from proofops.benchmark import run_benchmark


def test_repeatable_acceptance_benchmark():
    output = run_benchmark(2)
    assert output["runs"] == 6
    assert output["successes"] == 6
    assert output["all_passed"]
    assert output["is_ai_benchmark"] is False
    assert all(r["engine"] == "evidence-engine" for r in output["results"])
