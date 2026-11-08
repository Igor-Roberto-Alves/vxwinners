#!/usr/bin/env bash
# Sobe a API de sugestão de cadastro (porta 8700).
#
# ATENÇÃO: o fonte servico/api.py foi perdido — a API roda a partir do
# bytecode compilado (api.pyc, Python 3.13), junto com preenchimento/contrato.pyc
# e preenchimento/02_regras.pyc. Não apague esses .pyc.
#
# A venv com as dependências (fastapi, uvicorn, scikit-learn, pandas, scipy,
# joblib) está em ~/Hackathon_xv/.venv. Para usar outra, exporte PYTHON=/caminho/python.
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-$HOME/Hackathon_xv/.venv/bin/python}"
exec "$PYTHON" servico/api.pyc
