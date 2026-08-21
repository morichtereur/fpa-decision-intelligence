.PHONY: install extract backtest scenario report commentary eval-verifier test api web web-install template onboard readiness

# Prefer the project venv over whatever `python` happens to mean on PATH.
# Every target used to call a bare `python`, which does not exist on a modern
# macOS unless the venv is already activated — so the commands the README
# documents failed for anyone who followed it literally.
PY := $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)

install:       ; $(PY) -m pip install -r requirements-dev.txt
extract:       ; $(PY) -m src.extract
backtest:      ; $(PY) -m src.backtest
scenario:      ; $(PY) -m src.scenario
report:        ; $(PY) -m src.report
commentary:    ; $(PY) -m api.generate_commentary
eval-verifier: ; $(PY) -m eval.eval_verifier
test:          ; $(PY) -m pytest tests/ -q

# Client intake. `make template CLIENT=acme` writes a workbook to fill in;
# `make onboard FILE=...` turns the filled workbook into a client pack.
CLIENT ?= new_client
template:      ; $(PY) -m src.intake template --client $(CLIENT)
onboard:       ; $(PY) -m src.intake onboard $(FILE)
readiness:     ; $(PY) -c "from src import clientpack, readiness; import sys; \
                   p=clientpack.get_pack('$(CLIENT)' if '$(CLIENT)'!='new_client' else None); \
                   r=readiness.assess(p); print(r['summary']); \
                   [print(f\"  GAP  {g['question']}  ({g['detail']})\") for g in r['gaps']]"

# Interactive FP&A Decision Cockpit (api/ + web/) — see README "Run the cockpit".
api:           ; $(PY) -m uvicorn api.main:app --reload --port 8000
web-install:   ; cd web && npm install
web:           ; cd web && npm run dev
