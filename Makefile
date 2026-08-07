SHELL   := $(shell which bash)
SRCDIRS := $(addprefix $(PWD)/,drivers tests ush)
TARGETS := devenv docs env format lint rmenv test typecheck unittest

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
	@./run format $(SRCDIRS)

lint:
	@./run lint

rmenv:
	@./run rmenv

test: lint unittest # typecheck

typecheck:
	@./run typecheck $(SRCDIRS)

unittest:
	@./run unittest
