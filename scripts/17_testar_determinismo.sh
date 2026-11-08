#!/usr/bin/env bash
# Teste de determinismo (docs/13, V1.3): duas execucoes da extracao com as mesmas
# entradas tem de dar exatamente o mesmo resultado.
#
# Cada execucao roda numa pasta propria, com a sua copia do dicionario aprendido
# (congelado) e das respostas do LLM ja gravadas, e depois as duas sao
# comparadas registro a registro, caixa a caixa, e pelo plano de juncao.
#
# Uso: ./scripts/17_testar_determinismo.sh [--sem-bert] [--limite N]
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
PY=.venv/bin/python
EXTRA=()
for arg in "$@"; do EXTRA+=("$arg"); done
BASE=$(mktemp -d)

for v in a b; do
  d="$BASE/$v"; mkdir -p "$d"
  ln -s "$PWD/artefatos/pdm.json" "$d/pdm.json"
  [ -d artefatos/modelo_bert ] && ln -s "$PWD/artefatos/modelo_bert" "$d/modelo_bert"
  cp artefatos/aprendizado.json artefatos/desempate_llm.jsonl artefatos/deteccao_ausentes.jsonl "$d/"
  echo ">> execucao $v"
  $PY scripts/04_extrair.py --sem-llm --congelar-aprendizado --aplicar-desempates \
      --aplicar-deteccao --artefatos "$d" "${EXTRA[@]}" > "$d/log.txt" 2>&1
  $PY scripts/06_juntar.py --artefatos "$d" --exemplos 0 > "$d/juncao.txt" 2>&1
done

echo
$PY scripts/12_comparar_execucoes.py "$BASE/a" "$BASE/b" | head -20
falhou=0
for f in saneado_base.csv plano_juncao.csv; do
  if cmp -s "$BASE/a/$f" "$BASE/b/$f"; then echo "IDENTICO   $f"; else echo "DIFERENTE  $f"; falhou=1; fi
done
# o dicionario congelado nao pode ter mudado
if cmp -s "$BASE/a/aprendizado.json" artefatos/aprendizado.json; then echo "IDENTICO   aprendizado.json (congelado)"; else echo "DIFERENTE  aprendizado.json"; falhou=1; fi
echo "pastas: $BASE"
exit $falhou
