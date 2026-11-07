#!/usr/bin/env bash
# Sobe a plataforma inteira em localhost: API, modelos de sugestão e interface, tudo num servidor só.
#
#   ./rodar.sh                    sobe tudo e abre o navegador
#   ./rodar.sh --sem-navegador
#   PORTA=8100 ./rodar.sh         usa outra porta
#
# Na primeira vez prepara o ambiente, o banco (cerca de 1 minuto) e os modelos (cerca de 3 minutos).
# A etapa de LLM não roda aqui, porque gasta dinheiro: sem ela a base fica com a leitura só por regras.
# Ctrl+C encerra o servidor.
set -euo pipefail
cd "$(dirname "$0")"

PORTA="${PORTA:-8000}"
PY=backend/.venv/bin/python
URL="http://localhost:$PORTA/"

porta_livre(){ ! (exec 3<>/dev/tcp/127.0.0.1/"$PORTA") 2>/dev/null; }

# ---- ambiente ----------------------------------------------------------------
if [[ ! -x "$PY" ]]; then
  echo "[1/4] criando o ambiente em backend/.venv (Python 3.12)…"
  command -v python3.12 >/dev/null || { echo "ERRO: instale o Python 3.12."; exit 1; }
  python3.12 -m venv backend/.venv
  backend/.venv/bin/pip install --quiet -r backend/requirements.txt
else
  echo "[1/4] ambiente pronto"
fi

# ---- modelos de sugestão (gerados, não versionados) ---------------------------
if [[ ! -f servico/modelos/similares.joblib ]]; then
  echo "[2/4] treinando os modelos de sugestão (~3 min, só na primeira vez)…"
  [[ -f preenchimento/dados/base.csv ]] || "$PY" preenchimento/00_prep.py >/dev/null
  "$PY" servico/treina.py
else
  echo "[2/4] modelos prontos"
fi

# ---- banco --------------------------------------------------------------------
echo "[3/4] conferindo o banco…"
cd backend
../"$PY" -m app.cli migrar >/dev/null
materiais=$(../"$PY" -m app.cli contagens | awk '$1 == "material" {print $2}')
if [[ "${materiais:-0}" == 0 ]]; then
  echo "      base vazia: importando e lendo por regras (cerca de 1 minuto)…"
  ../"$PY" -m app.cli ingerir >/dev/null
  ../"$PY" -m app.cli estruturar --etapa regras >/dev/null
  ../"$PY" -m app.cli importar-preenchimento >/dev/null
fi

# ---- servidor -----------------------------------------------------------------
echo "[4/4] subindo o servidor…"
PID=""
encerrar(){ echo; echo "encerrando…"; [[ -n "$PID" ]] && kill "$PID" 2>/dev/null || true; exit 0; }
trap encerrar INT TERM

if porta_livre; then
  mkdir -p artefatos
  ../"$PY" -m uvicorn app.main:app --port "$PORTA" --log-level warning >artefatos/uvicorn.log 2>&1 &
  PID=$!
else
  echo "  aviso: a porta $PORTA já está em uso; reaproveitando o que está lá"
fi

printf '  aguardando a API'
ok=""
for _ in $(seq 60); do
  if curl -fsS -m 2 "http://localhost:$PORTA/saude" >/dev/null 2>&1; then ok=1; break; fi
  printf '.'; sleep 1
done
echo

if [[ -z "$ok" ]]; then
  echo "  ERRO: a API não respondeu. Log em backend/artefatos/uvicorn.log"
  [[ -n "$PID" ]] && kill "$PID" 2>/dev/null || true
  exit 1
fi

echo
echo "  ===> INTERFACE: $URL"
echo "  ===> API:       ${URL}docs"
echo
echo "  Busque em 'Buscar material', ou assuma um pedido em 'Pedidos de cadastro'."
echo "  Troque o usuário no topo para 'bia · revisora' para decidir exceções."
[[ -n "$PID" ]] && echo "  Ctrl+C encerra."

[[ "${1:-}" == "--sem-navegador" ]] || (command -v xdg-open >/dev/null && xdg-open "$URL" >/dev/null 2>&1 &) || true

[[ -n "$PID" ]] && wait "$PID"
exit 0
