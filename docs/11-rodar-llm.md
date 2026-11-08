# Como rodar o LLM

O LLM só roda **no Bedrock da AWS** (cliente em `src/saneamento/llm.py`,
credenciais no `.env`), e só no resíduo em que o texto **tem** o dado e o pipeline
ficou em dúvida. Ele não roda em registro "saneado e incompleto": ali o dado
não está no texto, e o modelo só poderia inventar.

## Onde ele atua

| Grupo | Registros (com BERT) | Script |
|---|---|---|
| Termo que o PDM não reconhece (`ZINC`, `MANOPLA`, `ACO ESPECIAL`) | ~650 | `11_canonizar_termos.py`, **por termo**, não por registro |
| CONFLITO: regra e BERT leram valores diferentes | ~730 | `10_desempatar_llm.py` |
| AMBÍGUO: o texto casa mais de um valor da lista | ~140 | `10_desempatar_llm.py` |

Os números exatos saem do `--so-contar` de cada script.

## A ordem

Cada passo lê o que o anterior gravou em `artefatos/`.

```bash
set -a; source .env; set +a          # credenciais do Bedrock

# 0. extracao completa, sem LLM (gera decisoes_base.jsonl)
.venv/bin/python scripts/04_extrair.py --sem-llm

# 1. canonizar TERMOS recusados pela lista: centavos, e o resultado vai para o
#    dicionario aprendido - vale para toda execucao seguinte, sem LLM
.venv/bin/python scripts/11_canonizar_termos.py --so-contar   # custo, sem chamar
.venv/bin/python scripts/11_canonizar_termos.py

# 2. extrair de novo: o dicionario agora resolve aqueles termos de graca
.venv/bin/python scripts/04_extrair.py --sem-llm

# 3. desempate dos CONFLITOS e AMBIGUOS que sobraram
.venv/bin/python scripts/10_desempatar_llm.py --so-contar     # custo, sem chamar
.venv/bin/python scripts/10_desempatar_llm.py                 # grava desempate_llm.jsonl

# 4. aplicar as respostas na base, sem chamar o LLM de novo
.venv/bin/python scripts/04_extrair.py --sem-llm --aplicar-desempates

# 5. juncao e catalogo
.venv/bin/python scripts/06_juntar.py
.venv/bin/python scripts/07_catalogo.py
```

## O que cada peça garante

- **Toda resposta do LLM passa pelo validador do PDM.** Valor fora da lista é
  recusado, venha de onde vier.
- **`--aplicar-desempates` só atua em caixas que ainda estão em dúvida** na
  extração atual. Uma resposta dada para uma extração anterior não sobrescreve
  um valor que a regra, o rótulo ou o BERT já resolvem hoje (teste
  `test_desempate_gravado_e_aplicado_so_onde_ainda_ha_duvida`).
- **Sem esse passo, o desempate ficaria só no arquivo.** O script 10 grava o
  `desempate_llm.jsonl` e alimenta o dicionário aprendido, mas o dicionário só
  guarda caixa textual. Os conflitos numéricos e de part number (~700 dos
  ~870) não chegariam ao `saneado_base.csv` nem ao catálogo.
- **O termo recortado fora da lista continua registrado.** O BERT não manda
  mais a proposta fora da lista para o árbitro (ela travava o registro), mas o
  trecho fica na decisão (`"bert"`, motivo "fora da lista do PDM"), e é dali que
  o script 11 o lê.
- **Cache em disco** (`artefatos/cache_llm/`): uma pergunta repetida não paga de
  novo.

## Custo de referência

Pelas medições do `00-estado-do-projeto.md` (Haiku 4.5): ~US$ 0,003 por
registro no desempate, e ~US$ 0,0003 por termo na canonização. Para o resíduo
acima, isso dá uns **US$ 3** no passo 3 e **menos de US$ 0,10** no passo 1. O
`--so-contar` dá o valor exato antes de qualquer chamada.

**Atenção: os dois `--so-contar` subestimam, e por motivos diferentes.** Os dois
usam um número fixo de tokens por chamada, chutado:

| Script | Assume | Medido | Desvio |
|---|---|---|---|
| `11` canonizar | 220 tokens de entrada por termo | ~1.300 (implícito no custo real) | ~6× |
| `10` desempate | 2.157 de entrada, 204 de saída por registro | 3.389 e 251, em log (rodada dos pedidos) | ~1,3× |

O chute do script 11 ignora o `SISTEMA` do próprio script (~520 tokens) e o `enum`
do atributo no tool use — é a explicação da nota no fim desta página. A medição
está em [`16-custo-de-llm.md`](16-custo-de-llm.md) §2, que também traz o gasto de
LLM do projeto inteiro e quanto custaria rodar LLM em tudo.

## Antes de apresentar

Conferir à mão uma amostra das caixas que o LLM resolveu (fonte `llm` no
`decisoes_base.jsonl`): o LLM é a camada menos reproduzível do pipeline, e é a
que a banca vai questionar primeiro.

## Primeira execução (2026-11-07)

Haiku 4.5 no Bedrock, sobre a extração oficial com BERT.

| Etapa | Resultado | Custo real |
|---|---|---|
| 11, canonização por termo | 939 termos, **17 aprendidos**, 921 recusados (quase todos rótulo, fragmento ou ambíguo de verdade: `COMPR`, `PN`, `ACO`, `ZINC`). 2 aprendidos estavam errados e foram removidos à mão do `aprendizado.json`: `BITOLA M8X1 → M8` (rosca fina vira grossa fora da barra roscada) e `ACABAMENTO ZINCADO → ZINCADO BRANCO` (variante inventada) | US$ 1,32 (a estimativa era US$ 0,32) |
| 10, desempate | 1.370 registros, **1.155 caixas aceitas** (77,6%), 274 `null` corretos, 60 recusadas pelo validador | US$ 5,53 |
| 04 `--aplicar-desempates` | 1.063 registros alterados | — |

| Indicador | Antes do LLM | Depois |
|---|---|---|
| SANEADO | 22.423 (95,2%) | **23.287 (98,9%)** |
| ↳ saneado e completo | 14.707 (62,4%) | **15.358 (65,2%)** |
| ↳ saneado e incompleto | 7.716 | 7.929 |
| PENDENTE | 265 | 130 |
| REVISAO_HUMANA | 829 (3,5%) | **100 (0,4%)** |
| Chaves fechadas | 16.590 | 16.810 |
| Códigos redundantes | 2.564 | **2.642** |
| Capital em código redundante | — | R$ 30,2 mi (15,0% do estoque) |

**Revisar antes de apresentar:**
- 130 clusters de junção têm ao menos um membro com valor decidido pelo
  LLM. Numa amostra de 8, um era suspeito: manômetro `0 A 16KGF/CM2` juntado
  com `0-16 BAR`. A faixa foi arredondada para o valor da lista, mas o mostrador
  impresso é outro. A FAIXA de manômetro em kgf/cm² não deveria fechar chave
  por conversão.
- A estimativa de custo do script 11 está 4 vezes abaixo do real.
- Melhorias para a próxima execução: filtrar rótulos (`COMPR`, `PN`, `COD`)
  antes do script 11, e a regra não reconhece `AMP` como ampère (`IN:40AMP` só
  foi resolvido pelo LLM).
