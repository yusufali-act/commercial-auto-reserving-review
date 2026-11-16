PY ?= .venv/bin/python

.PHONY: setup data splice test results notebooks all clean

setup:            ## create venv and install dependencies
	python3 -m venv .venv
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -r requirements.txt
	$(PY) -m pip install -q -e .

data:             ## download the CAS commercial auto file into data/raw/
	$(PY) -c "from reserving.data import download_cas; print(download_cas())"

splice:           ## regenerate the SPLICE claim-level data (needs R + SPLICE + arrow)
	Rscript data/generate_splice.R

test:             ## run the test suite
	$(PY) -m pytest -q

results: data     ## headline numbers -> outputs/results.json, outputs/tables/
	$(PY) -m reserving.pipeline

notebooks: data   ## execute all notebooks in place (regenerates outputs/figures/)
	cd notebooks && for nb in 0*.ipynb; do ../$(PY) -m jupyter nbconvert --to notebook --execute --inplace $$nb || exit 1; done

all: test results notebooks

clean:
	rm -rf outputs/figures/*.png outputs/tables/*.csv outputs/results.json
