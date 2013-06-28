PWD := $(shell pwd)
SOURCEDEPS_DIR ?= $(shell dirname $(PWD))/.sourcecode
HOOKS_DIR := $(PWD)/hooks
CHARM_DIR := $(PWD)
PYTHON := /usr/bin/env python


build: sourcedeps proof

revision:
	@test -f revision || echo 0 > revision

proof: revision
	@echo Proofing charm...
	@(charm proof $(PWD) || [ $$? -eq 100 ]) && echo OK
	@test `cat revision` = 0 && rm revision

sourcedeps: $(PWD)/config-manager.txt
	@echo Updating source dependencies...
	@$(PYTHON) cm.py -c $(PWD)/config-manager.txt \
		-p $(SOURCEDEPS_DIR) \
		-t $(PWD)

.PHONY: revision proof sourcedeps
