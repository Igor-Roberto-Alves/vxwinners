#!/usr/bin/env bash
# Cadeia completa, do xlsx ao catalogo, com os passos de LLM e as avaliacoes.
# Ver docs/13-plano-validacao.md (V1).
#
# Uso:
#   ./scripts/rodar_completo.sh               # reaproveita as respostas do LLM ja gravadas
#   ./scripts/rodar_completo.sh --com-llm     # chama o Bedrock (passos 5-7; custa ~US$ 20)
#   ./scripts/rodar_completo.sh --treinar     # treina o BERT antes (~40 min em CPU)
#   ./scripts/rodar_completo.sh --rapido      # so 3.000 registros, para testar mudanca
#   ./scripts/rodar_completo.sh --sem-bert    # sem o modelo (caixa LIVRE fica sem BERT)
#
# Sem --com-llm, os passos 5-7 nao rodam: o passo 8 aplica o desempate_llm.jsonl
# e o deteccao_ausentes.jsonl que estao em artefatos/ (versionados), e o
# dicionario aprendido e usado congelado. Assim duas execucoes dao o mesmo
# resultado (teste de determinismo em docs/13, V1.3).

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

PY=.venv/bin/python
ART=artefatos
COM_LLM=0; TREINAR=0; LIMITE=""; BERT=""

for arg in "$@"; do
  case "$arg" in
    --com-llm)  COM_LLM=1 ;;
    --treinar)  TREINAR=1 ;;
    --rapido)   LIMITE="--limite 3000" ;;
    --sem-bert) BERT="--sem-bert" ;;
    *) echo "argumento desconhecido: $arg"; exit 1 ;;
  esac
done

[ -x "$PY" ] || { echo "venv nao encontrado: veja docs/00-estado-do-projeto.md, secao 4"; exit 1; }
if [ -z "$BERT" ] && [ ! -d "$ART/modelo_bert" ] && [ "$TREINAR" = 0 ]; then
  echo "artefatos/modelo_bert/ nao existe (nao e versionado): use --treinar ou --sem-bert"; exit 1
fi
if [ "$COM_LLM" = 1 ]; then
  [ -f .env ] || { echo "--com-llm pedido mas .env nao existe (credenciais do Bedrock)"; exit 1; }
  set -a; source .env; set +a
  export AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
fi

passo() { echo; echo "######## $* ########"; echo; }
CONGELA="--congelar-aprendizado"

passo "0  testes";                       $PY -m pytest tests -q
passo "1  compilar o PDM";               $PY scripts/01_compilar_pdm.py
passo "2  rotulos de treino";            $PY scripts/02_gerar_rotulos.py | tail -5
if [ "$TREINAR" = 1 ]; then
  passo "3  treinar o BERT";             $PY scripts/03_treinar_bert.py --epocas 3 --lote 32 | tail -5
fi

if [ "$COM_LLM" = 1 ]; then
  # shellcheck disable=SC2086
  passo "4  extracao sem LLM";           $PY scripts/04_extrair.py --sem-llm $BERT $LIMITE $CONGELA
  passo "5  LLM: canonizar termos";      $PY scripts/11_canonizar_termos.py
  passo "6  LLM: desempate";             $PY scripts/10_desempatar_llm.py
  passo "7  LLM: ausente/generico";      $PY scripts/12_detectar_ausentes.py --amostra 100000
else
  passo "4-7  LLM pulado: aplicando as respostas gravadas em $ART/"
fi

# shellcheck disable=SC2086
passo "8  extracao aplicando o LLM";     $PY scripts/04_extrair.py --sem-llm $BERT $LIMITE $CONGELA \
                                           --aplicar-desempates --aplicar-deteccao
passo "9  completacoes sugeridas";       $PY scripts/14_sugerir_completacoes.py | tail -12
passo "10 juncao";                       $PY scripts/06_juntar.py --exemplos 0 | tail -14
passo "11 catalogo";                     $PY scripts/07_catalogo.py | tail -10

passo "12 avaliacoes"
UVPD="uv run -q --no-project --with pandas --with openpyxl python"
$UVPD scripts/16_avaliar_campos_cadastro.py | tail -3
if [ -f avaliacao/evaluate_caracteristicas.py ]; then $UVPD avaliacao/evaluate_caracteristicas.py || true; fi
if [ -f avaliacao/evaluate_cadastro.py ];       then $UVPD avaliacao/evaluate_cadastro.py || true; fi

passo "13 manifesto";                    $PY scripts/15_manifesto.py

echo
echo "PRONTO: $ART/catalogo_final.xlsx · $ART/plano_juncao.csv · $ART/manifesto.json"
