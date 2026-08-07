SHELL   := $(shell which bash)
SRCDIRS := $(addprefix $(PWD)/,drivers tests ush)
TARGETS := bootstrap devenv docs env format lint rmenv test typecheck unittest

.PHONY: $(TARGETS)

all:
	$(error Valid targets are: $(TARGETS))

bootstrap:
	@bin/run bootstrap

devenv:
	@DEVMODE=1 bin/run makeenv

docs:
	@bin/run makedocs

env:
	@bin/run makeenv

format:
	@bin/run format $(SRCDIRS)

lint:
	@bin/run lint

rmenv:
	@bin/run rmenv

test: lint unittest # typecheck

typecheck:
	@bin/run typecheck $(SRCDIRS)

unittest:
	@bin/run unittest
