#!/usr/bin/env bash
# Sobe a API de sugestão de cadastro (porta 8700).
#
# Usa a venv do próprio repositório (.venv). Se ela não existir, crie com:
#   python3 -m venv .venv && .venv/bin/pip install -r requirements-api.txt
#
# ATENÇÃO: o fonte servico/api.py foi perdido — a API roda a partir do
# bytecode compilado (api.pyc, Python 3.13), junto com preenchimento/contrato.pyc
# e preenchimento/02_regras.pyc. Não apague esses .pyc.
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-.venv/bin/python}"
if [ ! -x "$PYTHON" ]; then
  echo "venv não encontrada. Crie com:" >&2
  echo "  python3 -m venv .venv && .venv/bin/pip install -r requirements-api.txt" >&2
  exit 1
fi
exec "$PYTHON" servico/api.pyc
