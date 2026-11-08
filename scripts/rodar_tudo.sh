#!/usr/bin/env bash
# Roda a cadeia completa: PDM -> rotulos -> (treino) -> extracao -> juncao -> catalogo.
#
# Uso:
#   ./scripts/rodar_tudo.sh                  # usa o modelo BERT se existir; sem LLM
#   ./scripts/rodar_tudo.sh --com-llm        # liga o desempate por LLM no Bedrock
#   ./scripts/rodar_tudo.sh --treinar        # treina o BERT antes (28 min em CPU)
#   ./scripts/rodar_tudo.sh --rapido         # so 3.000 registros, para validar mudanca
#
# O resultado final e artefatos/catalogo_final.xlsx

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

PY=.venv/bin/python
ART=artefatos
TREINAR=0
LLM="--sem-llm"
LIMITE=""

for arg in "$@"; do
  case "$arg" in
    --treinar) TREINAR=1 ;;
    --com-llm) LLM="" ;;
    --rapido)  LIMITE="--limite 3000" ;;
    *) echo "argumento desconhecido: $arg"; exit 1 ;;
  esac
done

if [ ! -x "$PY" ]; then
  echo "venv nao encontrado. Crie com:"
  echo "  uv venv --python 3.12 .venv"
  echo "  uv pip install --python $PY --index-strategy unsafe-best-match \\"
  echo "    --extra-index-url https://download.pytorch.org/whl/cpu \\"
  echo "    torch transformers numpy scikit-learn openpyxl boto3 pytest"
  exit 1
fi

if [ -z "$LLM" ]; then
  if [ ! -f .env ]; then
    echo "--com-llm pedido mas .env nao existe (credenciais do Bedrock)"; exit 1
  fi
  set -a; source .env; set +a
  export AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
  echo ">> LLM ligado, regiao $AWS_REGION"
fi

passo() { echo; echo "######## $* ########"; echo; }

passo "0/6  testes"
$PY -m pytest tests/ -q

passo "1/6  compilar o PDM"
$PY scripts/01_compilar_pdm.py

passo "2/6  gerar rotulos de treino (distant supervision)"
$PY scripts/02_gerar_rotulos.py | tail -12

if [ "$TREINAR" = "1" ]; then
  passo "3/6  treinar o BERT  (~28 min em CPU; checkpoint por epoca)"
  $PY scripts/03_treinar_bert.py --epocas 3 --lote 32 2>&1 | tee "$ART/treino.log" \
    | grep -E "^  epoca [0-9]:|^  checkpoint|F1|Tempo de treino|Sequencia"
else
  if [ -d "$ART/modelo_bert" ]; then
    passo "3/6  treino pulado (modelo ja existe em $ART/modelo_bert)"
  else
    passo "3/6  treino pulado e SEM modelo: o pipeline rodara sem a camada BERT"
    echo "     caixas de tipo LIVRE (part number) ficarao vazias."
    echo "     Para treinar: ./scripts/rodar_tudo.sh --treinar"
  fi
fi

BERT="--sem-bert"
[ -d "$ART/modelo_bert" ] && BERT=""

passo "4/6  extrair: regras -> BERT -> arbitro -> LLM"
# shellcheck disable=SC2086
$PY scripts/04_extrair.py $BERT $LLM $LIMITE

passo "5/6  juntar por chave de identidade"
$PY scripts/06_juntar.py --exemplos 2

passo "6/6  montar o catalogo final"
$PY scripts/07_catalogo.py

echo
echo "================================================================"
echo " PRONTO"
echo "================================================================"
echo " catalogo ....... $ART/catalogo_final.xlsx"
echo " plano de juncao  $ART/plano_juncao.csv"
echo " auditoria ...... $ART/decisoes_base.jsonl"
echo " grades .......... $ART/caixas_base.jsonl  (rode scripts/05_encaixotar.py)"
echo
echo " para atualizar as telas que leem estes artefatos:"
echo "   scripts/19_fila_intervencao.py   fila de intervencao humana"
echo "   scripts/20_radar.py              radar (precisa rodar antes do 21)"
echo "   scripts/21_juncao_ncm.py         codigos juntados e NCM trocado"
