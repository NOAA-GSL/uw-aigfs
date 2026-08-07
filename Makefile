SHELL   := $(shell which bash)
SRCDIRS := $(addprefix $(PWD)/,drivers tests ush)
TARGETS := bootstrap devenv docs env format lint rmenv test typecheck unittest

.PHONY: $(TARGETS)

all:
	$(error Valid targets are: $(TARGETS))

bootstrap:
	@./run bootstrap

devenv:
	@DEVMODE=1 ./run makeenv

docs:
	@./run makedocs

env:
	@./run makeenv

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
