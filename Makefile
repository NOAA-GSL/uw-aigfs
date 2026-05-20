TARGETS = format lint test

.PHONY: $(TARGETS)

format:
	@./format

lint:
	ruff check drivers

test: lint unittest

unittest:
	pytest --cov tests
