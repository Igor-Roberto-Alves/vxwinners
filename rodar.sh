#!/usr/bin/env bash
# Sobe a plataforma inteira em localhost: API de sugestão + interface.
#
#   ./rodar.sh          sobe tudo e abre o navegador
#   ./rodar.sh --sem-navegador
#
# Ctrl+C encerra os dois servidores.
set -euo pipefail
cd "$(dirname "$0")"

PORTA_API=8700
PORTA_WEB=8080
DEPS=(--with pandas --with numpy --with scikit-learn --with joblib --with scipy
      --with openpyxl --with fastapi --with uvicorn --with pydantic)

command -v uv >/dev/null || { echo "ERRO: 'uv' não encontrado. Instale em https://docs.astral.sh/uv/"; exit 1; }

porta_livre(){ ! (exec 3<>/dev/tcp/127.0.0.1/"$1") 2>/dev/null; }

# ---- pré-requisitos (gerados, não versionados) -----------------------------
if [[ ! -f preenchimento/dados/base.csv ]]; then
  echo "[1/3] preparando dados (converte os xlsx e congela os splits)…"
  (cd preenchimento && uv run --quiet "${DEPS[@]}" python 00_prep.py >/dev/null)
else
  echo "[1/3] dados já preparados"
fi

if [[ ! -f servico/modelos/similares.joblib ]]; then
  echo "[2/3] treinando os modelos (~3 min, só na primeira vez)…"
  (cd servico && uv run --quiet "${DEPS[@]}" python treina.py)
else
  echo "[2/3] modelos já treinados"
fi

# ---- servidores -------------------------------------------------------------
echo "[3/3] subindo servidores…"
PIDS=()
encerrar(){ echo; echo "encerrando…"; for p in "${PIDS[@]:-}"; do kill "$p" 2>/dev/null || true; done; exit 0; }
trap encerrar INT TERM

if porta_livre "$PORTA_API"; then
  (cd servico && uv run --quiet "${DEPS[@]}" python -m uvicorn api:app \
      --host 127.0.0.1 --port "$PORTA_API" >/tmp/vx-api.log 2>&1) &
  PIDS+=($!)
else
  echo "  aviso: porta $PORTA_API já em uso — reaproveitando o que está lá"
fi

if porta_livre "$PORTA_WEB"; then
  python3 -m http.server "$PORTA_WEB" --bind 127.0.0.1 >/tmp/vx-web.log 2>&1 &
  PIDS+=($!)
else
  echo "  aviso: porta $PORTA_WEB já em uso — reaproveitando o que está lá"
fi

# a API carrega os modelos no startup; espera ficar de pé
URL="http://127.0.0.1:$PORTA_WEB/mockup_plataforma.html"
printf '  aguardando a API'
for _ in $(seq 60); do
  if curl -fsS -m 2 "http://127.0.0.1:$PORTA_API/saude" >/dev/null 2>&1; then ok=1; break; fi
  printf '.'; sleep 1
done
echo

if [[ "${ok:-}" == 1 ]]; then
  echo "  API   http://127.0.0.1:$PORTA_API/saude  ·  $(curl -fsS "http://127.0.0.1:$PORTA_API/saude")"
else
  echo "  AVISO: a API não respondeu. A interface abre, mas em modo mockup."
  echo "         log em /tmp/vx-api.log"
fi

echo
echo "  ===> INTERFACE: $URL"
echo
echo "  Vá em 'Cadastro de item' (barra lateral) e cole um pedido, ou use"
echo "  'Usar outro exemplo'. A tela 'Busca de materiais' também usa a API."
echo "  Ctrl+C encerra."

[[ "${1:-}" == "--sem-navegador" ]] || (command -v xdg-open >/dev/null && xdg-open "$URL" >/dev/null 2>&1 &) || true

wait
