SHELL   = $(shell /usr/bin/env bash)
TARGETS = devenv docs env format lint rmenv test unittest

.PHONY: $(TARGETS)

all:
	$(error Valid targets are: $(TARGETS))

devenv:
	@DEVMODE=1 ./run bootstrap

docs:
	@./run docs

env:
	@./run bootstrap

format:
	@bin/format $(addprefix $(PWD),drivers tests ush)

lint:
	ruff check .

rmenv:
	@./run rmenv

test: lint unittest

unittest:
	pytest --cov tests
