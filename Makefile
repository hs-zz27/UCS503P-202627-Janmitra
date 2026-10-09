.PHONY: docs docserve docbuild
# Install documentation dependencies first: python -m pip install -e ".[docs]"
docs: docserve
docserve:
	python -m mkdocs serve
docbuild:
	python -m mkdocs build
