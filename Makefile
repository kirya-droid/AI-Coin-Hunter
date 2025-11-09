.PHONY: venv install run-once run-interval

venv:
	python -m venv .venv

install:
	. .venv/bin/activate || . .venv/Scripts/activate && pip install -r requirements.txt

run-once:
	python -m src.main once

run-interval:
	python -m src.main interval
