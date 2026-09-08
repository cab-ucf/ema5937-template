# Makefile for doing full analysis and creating report
# Recipes have this form:
# 'output: input1 input2 input3'
# '	recipe line 1'
# 
# The recipes here are:
# 1) Run ETL to get parquet file (Automatic variable '$@' is output - 'data/datset.parquet' here)
# 2) Run analysis to get results (Automatic variable '$<' first input - 'data/dataset.parquet' here)
# 3) Create report pdf from typst
#
# make all                        -> report/main.pdf from nothing (sample data)
# make all CONFIG=config.hpc.yaml -> same, all shards (what the Slurm job runs)
CONFIG ?= config.yaml

all: report/main.pdf

data/dataset.parquet: src/mseml/etl.py $(CONFIG)
	uv run python -m mseml.etl $(CONFIG) $@

results/results.json: data/dataset.parquet src/mseml/analysis.py $(CONFIG)
	uv run python -m mseml.analysis $(CONFIG) $< figures results/results.json

report/main.pdf: results/results.json report/main.typ report/refs.bib
	typst compile --root . report/main.typ $@
