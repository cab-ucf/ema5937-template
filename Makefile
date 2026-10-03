# Makefile for doing full analysis and creating report
# Recipes have this form:
# 'output: input1 input2 input3'
# '	recipe line 1'
# 
# The recipes here are:
# 1) Run ETL to get the database (Automatic variable '$@' is output - 'data/dataset.db' here)
# 2) Run analysis to get results (Automatic variable '$<' first input - 'data/dataset.db' here)
# 3) Create report pdf from typst
#
# make all                        -> report/main.pdf from nothing (sample data)
# make all CONFIG=config.hpc.yaml -> same, all plates (what the Slurm job runs)
CONFIG ?= config.yaml

all: report/main.pdf

data/dataset.db: src/mseml/etl.py schema.sql $(CONFIG)
	uv run python -m mseml.etl $(CONFIG) $@

results/results.json: data/dataset.db src/mseml/analysis.py $(CONFIG)
	uv run python -m mseml.analysis $(CONFIG) $< figures results/results.json

report/main.pdf: results/results.json report/main.typ report/refs.bib
	typst compile --root . report/main.typ $@
