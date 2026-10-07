.PHONY: test lint type-check

test:
	python -m pytest

lint:
	ruff check src tests examples

type-check:
	mypy src
