# linting rules

lint: lint-markdown

lint-markdown:
    uvx rumdl check .

# format rules

fmt: fmt-markdown

fmt-markdown:
    uvx rumdl fmt .

# management rules

init:
    uvx pre-commit install

update:
    uvx pre-commit autoupdate
