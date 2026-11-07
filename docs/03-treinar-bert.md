# Treinar o extrator BERT — guia para a máquina de treino

Este documento é autossuficiente: quem receber o repositório consegue treinar sem
precisar de contexto adicional. O treino **não** roda na máquina de
desenvolvimento (CPU, 8 núcleos, sem GPU) — foi interrompido de propósito e
movido para cá.

```bash
# resumo, para quem só quer rodar
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python torch transformers numpy scikit-learn openpyxl
.venv/bin/python scripts/03_treinar_bert.py --epocas 3 --lote 16
# devolver o diretório artefatos/modelo_bert/
```

---

## 1. O que é o modelo

**Classificação de token (token classification) com esquema BIO.** Não é
geração, não é classificação de sentença, não é embedding.

| | |
|---|---|
| Tarefa | rotular cada palavra da descrição com o atributo a que ela pertence |
| Espaço de rótulos | **187 tags** = `O` + `B-`/`I-` para cada um dos **93 nomes de atributo** do PDM |
| Entrada | lista de palavras já normalizadas (maiúsculas, sem acento) |
| Saída | uma tag por palavra, agrupada depois em `atributo → valor` |
| Modelo base | `distilbert-base-multilingual-cased` (padrão) |
| Parâmetros | ~135M |

O que ele faz, concretamente:

```
entrada    RETENTOR  110MM              15MM       BASL    NBR
saída      O         B-DIAMETRO EIXO    B-LARGURA  B-TIPO  B-MATERIAL
```

Os 93 nomes de atributo são **globais**, compartilhados entre as 44 classes do
PDM: `DIAMETRO INTERNO` é uma única tag, usada por rolamento, mangueira e
arruela. Isso multiplica os exemplos de treino por rótulo. Na inferência o
pipeline mascara a saída pelos atributos válidos da classe prevista, então não
há risco de atribuir `TENSAO ISOLAMENTO` a um parafuso.

---

## 2. Por que treinar isto

A pergunta certa não é "BERT é bom?", é "o que ele faz que as camadas mais
baratas não fazem?". Tudo abaixo foi medido na base real (23.554 registros),
não estimado.

### 2.1 O que as regras já resolvem (e por isso não precisa de modelo)

| Camada | Cobertura medida |
|---|---|
| **74,9%** dos atributos obrigatórios têm lista de valores permitidos no PDM | casamento por dicionário, 0,98 de confiança |
| Casamento literal nas caixas textuais obrigatórias | **70,1%** (piso) |
| Grandezas com formato fixo (MM, POL, BAR, MM2) | gramática/regex |

Então o modelo **não** é para o caso fácil. Se fosse treinado para isso, estaria
substituindo com incerteza algo que já é determinístico.

### 2.2 O que só um modelo aprendido resolve: ambiguidade posicional

O caso canônico, e o motivo principal do treino:

```
RET. 110MM 15MM BASL NBR
```

A classe `RETENTOR` (PDM032) exige três grandezas, todas em MM:
`DIAMETRO EIXO`, `DIAMETRO ALOJAMENTO`, `LARGURA`. O texto traz **dois**
números. Qual é qual?

- A **gramática** acha dois números e três caixas: não consegue atribuir, marca
  ambíguo. Medido na base: **397 registros** com descasamento entre número de
  grandezas e número de caixas (contra 782 em que a contagem casa e a regra
  resolve).
- A **restrição de domínio** (alojamento > eixo > largura) resolve quando a
  contagem casa — já está implementada em `regras.py` e cobre os 782.
- O **modelo** aprende a convenção de ordem com os 61.869 exemplos
  auto-rotulados e resolve também quando falta número.

Essa é a diferença de capacidade. Não é ganho marginal de acurácia: é uma classe
de caso que nenhuma regra alcança.

Outros casos na mesma categoria: part number e modelo de equipamento
(`REFERENCIA FABRICANTE`, formato livre — 2.322 exemplos de treino), onde não há
lista de valores nem formato numérico para casar.

### 2.3 Por que não embedding

Medido com `intfloat/multilingual-e5-small` sobre o vocabulário real do PDM:

```
cos(ACO INOX 304, ACO INOX 316) = 0,963      ← não podem ser confundidos
cos(ROSCA NPT,    ROSCA BSP)    = 0,965
cos(DIN 931,      DIN 933)      = 0,959
cos(150#,         300#)         = 0,944
```

E os erros diretos: `NITRILICA` → `ACO CARBONO` (0,837; deveria ser `NBR`),
`VITON` → `ACO CARBONO`, `HDG` → `ORGANOMETALICO`, `DIN931` → `DIN 933`.

O embedding aproxima o que precisa ficar separado e não sabe o vocabulário
técnico. Ele serve para *blocking* na deduplicação (gerar pares candidatos), não
para decidir valor. E, principalmente: **embedding não recorta**. Ele precisa
receber um trecho já atribuído a uma caixa — e quem faz esse recorte é o BERT.

### 2.4 Por que não LLM para esta tarefa

A LLM é melhor que o embedding para canonizar valor, isso está medido e não se
discute. Mas para o **recorte em volume** ela é a escolha errada aqui:

| | BERT treinado | LLM por registro |
|---|---|---|
| 23.554 registros | segundos (CPU) | horas + custo |
| Reprodutibilidade | mesma entrada, mesma saída | não garantida |
| Iteração no hackathon | 50 execuções por dia | 2 ou 3 |
| Auditoria | tag + probabilidade por token | texto de justificativa |

A LLM continua no pipeline, mas na **camada 4**: só nos registros que o árbitro
escala (conflito entre regra e BERT, ambiguidade de dicionário, sujeito
incerto) e nos 520 pedidos de cadastro, onde o volume é pequeno e o formato é
irregular. Essa divisão está implementada em `arbitro.py` e testada.

### 2.5 A evidência de que funciona

O treino rodou **1 época de 3** nesta máquina antes de ser interrompido:

```
época 1: perda 1,157 → F1 por token 0,972 → sequência 100% correta 0,820
```

97,2% de F1 por token e 82% de sequências perfeitas **com um terço do treino**,
em CPU, com rótulos que não custaram anotação manual. É o número que justifica
terminar o treino numa máquina adequada.

---

## 3. Os dados de treino: rótulos de graça

Nenhuma linha foi anotada à mão. **59,9% dos registros da base já trazem pares
explícitos `ATRIBUTO: VALOR` na descrição longa** — resquício de quem cadastrou
seguindo o padrão. Isso é *distant supervision*.

| | |
|---|---|
| Registros auto-rotulados aproveitados | **11.511** (48,9% da base) |
| Anotações atributo-valor | **61.869** |
| Atributos distintos cobertos | **89** de 93 |
| Tokens por exemplo | média 7,1 · p95 12 · máx 21 |
| Treino / validação | **10.359 / 1.152** |

### O detalhe que faz o treino funcionar

**O nome do atributo é removido do texto de treino.** Se ficasse, o modelo
aprenderia apenas "copie o que vem depois dos dois pontos" — e seria inútil nos
registros telegráficos, que são exatamente o alvo.

```
descrição original na base
  PARAFUSO SEXTAVADO, ROSCA: MA, BITOLA: M-20, COMPRIMENTO: 250MM, CLASSE: 5.8

exemplo de treino gerado (rótulos fora do texto, só os valores, na ordem)
  PARAFUSO   O
  SEXTAVADO  O
  MA         B-ROSCA
  M-20       B-BITOLA
  250MM      B-COMPRIMENTO
  5.8        B-CLASSE RESISTENCIA
```

A entrada passa a ter a mesma distribuição do texto cru que o modelo vai
encontrar em produção. Sem isso, as métricas ficariam ótimas e o modelo não
serviria para nada — é o erro clássico de distant supervision e vale conferir
que não voltou, se alguém mexer em `rotulos.py`.

Há também **dropout de 0,15 na geração**: 15% dos atributos são descartados de
propósito, ensinando o modelo a deixar caixa vazia em vez de forçar
preenchimento. Isso importa porque 33% dos atributos obrigatórios da base estão
genuinamente ausentes, e um modelo que sempre preenche inventa dado.

A divisão treino/validação é **por `CODIGO_MATERIAL`**, nunca por linha, para
não vazar o mesmo item entre os dois lados.

---

## 4. Arquivos

### Levar para a máquina de treino

| Arquivo | Tamanho | Obrigatório |
|---|---|---|
| `artefatos/treino.jsonl` | 2,4 MB | **sim** |
| `artefatos/validacao.jsonl` | 272 KB | **sim** |
| `artefatos/pdm.json` | 81 KB | **sim** (define os 93 rótulos) |
| `src/saneamento/` | — | **sim** (`bert.py`, `pdm.py`, `rotulos.py`) |
| `scripts/03_treinar_bert.py` | — | **sim** |
| `dados/*.xlsx` | 2,7 MB | só se for regerar os rótulos |

Os três `.jsonl`/`.json` são determinísticos (semente 42). Copiar é mais seguro
que regerar. Se quiser regerar na outra máquina:

```bash
.venv/bin/python scripts/01_compilar_pdm.py     # dados/03_...xlsx -> artefatos/pdm.json
.venv/bin/python scripts/02_gerar_rotulos.py    # base -> treino.jsonl + validacao.jsonl
```

### Devolver

| Caminho | Conteúdo |
|---|---|
| `artefatos/modelo_bert/` | pesos, tokenizer, `rotulos.json`, `metricas.json` |

Tamanho esperado: ~540 MB em fp32. Se for incômodo transportar, salvar em
`safetensors` já é o padrão do `save_pretrained`; para encolher, converter para
fp16 na máquina de treino reduz à metade sem perda mensurável nesta tarefa.

**Não commitar o modelo no git.** Adicionar ao `.gitignore`:
```
artefatos/modelo_bert/
artefatos/cache_llm/
artefatos/*.csv
```

---

## 5. Ambiente

Python **3.12**. Não use 3.13+: o torch ainda não tem wheel para 3.14, que é o
Python do sistema na máquina de desenvolvimento (foi o motivo do venv separado).

```bash
uv venv --python 3.12 .venv
```

**CPU:**
```bash
uv pip install --python .venv/bin/python \
  --index-strategy unsafe-best-match \
  --extra-index-url https://download.pytorch.org/whl/cpu \
  torch transformers numpy scikit-learn openpyxl
```

**GPU (CUDA 12.x):**
```bash
uv pip install --python .venv/bin/python \
  torch transformers numpy scikit-learn openpyxl
```

Versões em que rodou: `torch 2.15.0+cpu`, `transformers 5.22.2`. O laço de
treino é **PyTorch puro, sem `Trainer`**, justamente para não quebrar com
mudança de API entre versões de `transformers`.

O modelo base é baixado do Hugging Face na primeira execução (~500 MB). Com
rede restrita, baixar antes e apontar `--modelo` para o diretório local. Definir
`HF_TOKEN` evita rate limit.

---

## 6. Comando e hiperparâmetros

```bash
.venv/bin/python scripts/03_treinar_bert.py --epocas 3 --lote 16 --lr 5e-5
```

| Flag | Padrão | Observação |
|---|---|---|
| `--epocas` | 3 | 1 época já deu F1 0,972. Com GPU, rodar 4–5 e ficar com a melhor validação |
| `--lote` | 16 | Em GPU subir para 64 ou 128 e escalar o `lr` junto |
| `--lr` | 5e-5 | Padrão de fine-tuning de BERT. Agendador `OneCycleLR`, 10% de warmup |
| `--max-len` | 96 | **Pode cair para 32.** p95 = 12 tokens, máximo 21. Isso acelera muito e não perde nada |
| `--modelo` | `distilbert-base-multilingual-cased` | Ver variantes abaixo |
| `--semente` | 42 | Mesma semente, mesmo modelo |
| `--destino` | `artefatos/modelo_bert` | |

O ganho mais barato é **`--max-len 32`**: o padrão de 96 está pagando atenção
sobre padding em 3/4 do tensor. Em CPU isso sozinho deve dar ~2× de velocidade.

---

## 7. Tempo esperado

Medido nesta máquina (8 núcleos, 4 threads do torch, sem GPU):

```
650 passos em ~20 min  ->  ~0,54 passo/s
3 épocas = 1.944 passos ->  ~60 min
```

| Hardware | 3 épocas (estimativa) |
|---|---|
| CPU 4 threads, `max_len 96` | ~60 min |
| CPU 4 threads, `max_len 32` | ~25–30 min |
| GPU T4 / RTX 3060 | ~3–5 min |
| GPU A100 | < 2 min |

Com GPU o treino é tão rápido que vale rodar as variantes da seção 9 e comparar,
em vez de aceitar a primeira configuração.

---

## 8. Como saber se ficou bom

O script imprime e grava em `modelo_bert/metricas.json`:

| Métrica | Referência (1 época, CPU) | Alvo |
|---|---|---|
| F1 por token (tokens de atributo) | **0,972** | ≥ 0,97 |
| Sequência 100% correta | **0,820** | ≥ 0,88 |
| Acurácia por token | — | ≥ 0,98 |

Precisão e recall são calculados **só sobre tokens que são atributo**, ignorando
`O`. Medir com `O` incluído inflaria tudo, porque a maioria dos tokens é `O`.

### Métrica não basta: confira a predição

Depois do treino, rodar o pipeline e olhar os casos difíceis. Este é o teste que
importa de verdade:

```bash
.venv/bin/python scripts/04_extrair.py --sem-llm --limite 3000
```

E conferir à mão, no `artefatos/decisoes_base.jsonl`, dois registros:

1. **`12711820`** — `RET. 110MM 15MM BASL NBR`, cadastrado no grupo errado
   (TUB01). O modelo deve dizer qual dos dois números é `DIAMETRO EIXO`. É o
   caso que justifica o treino: se ele errar aqui, o treino não entregou o que
   deveria, independentemente do F1.
2. **`27827726`** — `ANEL EXPULSOR ... COD FABRICANTE MM2905816`. O modelo deve
   recortar `MM2905816` como `REFERENCIA FABRICANTE` (a regra não consegue: é
   formato livre).

Comparar o antes e o depois com o baseline determinístico:

```bash
.venv/bin/python scripts/04_extrair.py --sem-bert --sem-llm --limite 3000
```

Baseline determinístico medido sem BERT, nos 3.000 primeiros registros — são os
números a bater:

| Indicador | Só regras |
|---|---|
| SANEADO (todos os obrigatórios preenchidos) | **16,8%** |
| PENDENTE (falta obrigatório) | 76,5% |
| REVISAO_HUMANA (conflito) | 1,8% |
| FORA_DO_PDM (sem classe) | 4,9% |
| Completude média dos obrigatórios | **0,680** |
| Escalariam para a LLM | 8,2% |

Se o BERT não mexer em `SANEADO` e em `completude`, o problema está na
integração, não no treino. O ganho deve aparecer principalmente nas caixas de
formato livre (`REFERENCIA FABRICANTE`, `MODELO EQUIPAMENTO`) e nas grandezas
com ambiguidade posicional, que são as duas coisas que a regra não alcança.

Os 60 testes continuam tendo de passar — eles cobrem as invariantes do PDM, que
não dependem do modelo:

```bash
.venv/bin/python -m pytest tests/ -q
```

---

## 9. Variantes que valem testar, em ordem de custo-benefício

1. **`--max-len 32`** — ganho puro de velocidade, risco zero (p95 = 12 tokens).
2. **`--epocas 5`** — a curva ainda estava caindo quando foi interrompida
   (1,16 na época 1, instantânea em 0,078). Guardar a melhor época por validação.
3. **`--modelo neuralmind/bert-base-portuguese-cased`** (BERTimbau) — treinado
   em português, deve ganhar 2–5 pontos de sequência exata. Mais lento: 12
   camadas contra 6 do DistilBERT. Só vale com GPU.
4. **Dropout na geração de rótulos** — `DROPOUT` em `scripts/02_gerar_rotulos.py`
   está em 0,15. Testar 0,25 para o modelo ser mais conservador ao deixar caixa
   vazia; 0,05 para ser mais agressivo ao preencher.
5. **`--lote 64 --lr 1e-4`** — só com GPU.

Registrar o resultado de cada variante: `metricas.json` guarda `config` junto
com as métricas, então basta mudar `--destino` por variante.

---

## 10. Onde o modelo entra no pipeline

O pipeline tem quatro camadas (`docs/02-plano-projeto.md`). O modelo é a 2:

```
1  regras.py        gazetteer do PDM + gramática de grandezas    determinístico
2  bert.py          RECORTA qual trecho pertence a qual caixa    ← este treino
3  arbitro.py       mede discordância entre 1 e 2, decide escalar
4  llm.py           Claude no Bedrock, só no resíduo escalado
   validador.py     invariantes do PDM: portão final de todo valor
```

Consumo, depois de devolver o diretório:

```python
from saneamento import Pdm, ExtratorBert, Pipeline

pdm  = Pdm.carregar("artefatos/pdm.json")
bert = ExtratorBert(pdm.nomes_atributos).carregar("artefatos/modelo_bert")
pipe = Pipeline(pdm, bert=bert)
```

Ponto importante: **o modelo não tem passe livre.** Todo valor que ele propõe
passa por `validador.py`, que recusa o que não está na lista de valores
permitidos do PDM. Vale para o BERT e vale para a LLM — é o que impede
alucinação de chegar na base (`tests/test_pipeline.py::test_llm_tambem_passa_pelo_validador`).

---

## 11. Limites conhecidos

- **4 atributos sem nenhum exemplo de treino**: `ALTURA`, `CLASSE`,
  `CORRENTE AC3`, `TENSAO`. Dependem de regra e LLM; o modelo nunca vai prever
  essas tags.
- **O rótulo herda o erro da base.** Distant supervision copia o que está
  escrito, inclusive o que está errado. Aparece ruído real nos exemplos (um
  `MATERIAL` com valor `- VER DESENHO`). Não corrigir isso à mão: é a
  distribuição verdadeira, e o validador barra na saída.
- **Classes desbalanceadas.** `PDM001` (parafuso sextavado) tem 1.823 exemplos;
  classes de baixo volume têm poucas dezenas. O modelo vai ser pior nas
  pequenas, e é esperado — elas são 610 registros no total.
- **O modelo não decide duplicidade.** Ele preenche as caixas; a identidade sai
  de igualdade de chave em `validador.chave_identidade` (regra 10 do PDM). Isso
  é deliberado: duplicidade tem de ser explicável como "estes dois códigos têm
  os mesmos valores nos atributos obrigatórios", não como "o modelo achou
  parecido".
- **O que o modelo não pode resolver**: 33% dos atributos obrigatórios estão
  genuinamente ausentes do texto. Medição do vocabulário não resolvido: 6.931
  trechos distintos para 9.332 ocorrências (1,3×), distribuição plana, e os mais
  frequentes são `MATERIAL = 'NAO UTILIZAR'` e `BITOLA = 'PARAFUSO SEXTAVADO'` —
  ou seja, texto errado na caixa, não sinônimo. Esses casos são **pendência e
  enriquecimento**, não extração. Nenhum modelo, nem BERT nem LLM, deve
  preencher ali.
