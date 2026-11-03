from bravon_false_green_benchmark import evaluate_cases, main


def test_benchmark_covers_both_false_green_families():
    result = evaluate_cases()
    assert result["total"] == 5
    assert result["correct"] == 5
    assert result["false_verified"] == 0
    assert {x["case"] for x in result["cases"] if x["actual"] == "CONTRADICTED"} == {
        "false_green_boundary", "false_green_accounting", "failed_original"
    }


def test_benchmark_explicitly_disclaims_real_world_generalization():
    assert "not a real-world accuracy estimate" in evaluate_cases()["disclaimer"]


def test_green_only_baseline_misses_false_repairs():
    outcome = evaluate_cases()
    assert outcome["baseline"]["correct"] == 2
    assert outcome["baseline"]["false_verified"] == 3
    assert outcome["correct"] == 5
    assert outcome["false_verified"] == 0
