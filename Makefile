PYTHON ?= python

.PHONY: help demo test prod

help:
	@echo "make demo  Generate the offline Phase 1 dataset"
	@echo "make test  Verify fixture integrity and expected costs"
	@echo "make prod  Reserved; production execution is not implemented"

demo:
	$(PYTHON) data/generator.py

test:
	$(PYTHON) -m unittest discover -s tests -v

prod:
	@echo "Production execution is not implemented. See docs/PLAN.md."
	@exit 1

