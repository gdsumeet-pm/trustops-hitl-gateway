.PHONY: install eval test api ui

install:
	pip install -r requirements.txt

eval:
	PYTHONPATH=. python3 evals/run_evals.py

test:
	PYTHONPATH=. pytest tests/ -v

api:
	PYTHONPATH=. uvicorn src.main:app --reload --port 8000

ui:
	PYTHONPATH=. streamlit run ui/app.py
