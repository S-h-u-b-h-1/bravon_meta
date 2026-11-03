.PHONY: run test benchmark
run:
	python -m uvicorn proofops.api:app --host 127.0.0.1 --port 8000

test:
	python -m pytest -q

benchmark:
	python -m proofops.benchmark --repeats 10 --output docs/latest-benchmark.json
