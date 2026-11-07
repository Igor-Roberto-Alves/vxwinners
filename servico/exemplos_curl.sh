#!/usr/bin/env bash
# Exemplos de chamada da API de sugestao (porta 8700).
# Suba antes: cd servico && python3 -m uvicorn api:app --host 127.0.0.1 --port 8700
set -euo pipefail
B=http://127.0.0.1:8700

echo '== GET /saude =='
curl -s "$B/saude"; echo

echo '== POST /sugerir (sem grupo informado) =='
curl -s -X POST "$B/sugerir" -H 'Content-Type: application/json' \
  -d '{"descricao": "ROLAMENTO RIGIDO DE ESFERAS SKF 6205-2Z FURO 25MM"}'; echo

echo '== POST /sugerir (com grupo informado) =='
curl -s -X POST "$B/sugerir" -H 'Content-Type: application/json' \
  -d '{"descricao": "PARAFUSO CAB SEXTAVADA BITOLA M14 COMP 50MM INOX", "grupo": "FIX01"}'; echo

echo '== POST /similares =='
curl -s -X POST "$B/similares" -H 'Content-Type: application/json' \
  -d '{"descricao": "PARAFUSO CAB SEXTAVADA BITOLA M14 COMP 50MM INOX"}'; echo

echo '== descricao vazia -> 422 =='
curl -s -o /dev/null -w '%{http_code}\n' -X POST "$B/sugerir" \
  -H 'Content-Type: application/json' -d '{"descricao": "   "}'
