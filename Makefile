ACTIVATE = . $(CONDADIR)/etc/profile.d/conda.sh && conda activate
CONDADIR = $(if $(CONDADIR),$(CONDADIR),$(PWD)/conda)
ENVNAME  = $(shell sed -n '/^name:.*/ s/^name: *//p' environment.yaml)
SHELL    = $(shell /usr/bin/env bash)
TARGETS  = devenv docs env format lint rmenv test unittest

.PHONY: $(TARGETS)

all:
	$(error Valid targets are: $(TARGETS))

devenv:
	@CONDADIR=$(CONDADIR) DEVMODE=1 bin/setup

docs:
	@CONDADIR=$(CONDADIR) bin/docs

env:
	@CONDADIR=$(CONDADIR) bin/setup

format:
	@bin/format $(addprefix $(PWD),drivers tests ush)

lint:
	ruff check .

rmenv:
	conda env remove -y -n $(ENVNAME)

test: lint unittest

unittest:
	pytest --cov tests
