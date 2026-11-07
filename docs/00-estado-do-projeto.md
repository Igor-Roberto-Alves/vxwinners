# Estado do projeto

Hackathon VX, Desafio 01 — Cadastro e saneamento de materiais.
Última atualização: 2026-11-07.

Este é o documento de entrada. Ele diz o que existe, o que foi medido, o que
ainda não funciona e onde está cada coisa. Para entender **como** o pipeline
funciona, leia `04-como-funciona.md`.

---

## 1. O problema, em um parágrafo

A base tem 23.554 materiais cadastrados ao longo de 22 anos por 260 usuários,
cada um escrevendo do seu jeito. O mesmo item aparece com vários códigos, vários
estoques e várias compras. A empresa tem um padrão escrito (PDM) que define 44
classes de material e 229 características, mas 79% das descrições não o seguem.
O trabalho é transformar cada linha de texto numa estrutura padronizada e, a
partir dela, provar quais códigos são o mesmo item.

A solução cabe em uma frase: **transformar cada linha numa grade de caixas;
quando duas grades têm as mesmas caixas, é o mesmo item.**

---

## 2. Números medidos

Tudo abaixo saiu de execução real sobre os 23.554 registros, não de estimativa.

### Pipeline determinístico (regras + dicionário, sem modelo)

| Indicador | Valor |
|---|---|
| Linhas que recebem classe do PDM | **97,0%** |
| Completude média das caixas obrigatórias | **0,759** |
| SANEADO (todas as caixas obrigatórias cheias) | **34,0%** |
| Descrição no formato PDM | 97,0% (era 20,7%) |
| NCM presente e no formato `0000.00.00` | 22.281 (era 13.901) |
| Chave de identidade fechada | 8.694 |
| **Códigos redundantes com justificativa auditável** | **876** |
| Capital em código redundante | **R$ 13,72 mi** (6,8% do estoque) |
| Valor negociável em conjunto (777 clusters multicentro) | R$ 21,83 mi |
| Velocidade | ~700 registros/s |

### Com o BERT ligado

| Indicador | Só regras | Com BERT |
|---|---|---|
| Completude média | 0,759 | **0,814** |
| Chave de identidade fechada | 8.694 | **12.848** |
| Códigos redundantes | 876 | **1.657** |
| Velocidade | 700 reg/s | 33 reg/s (CPU) |

**A junção quase dobrou com o BERT.** É o resultado principal do dia.

> Em reprocessamento: a última execução ainda usa a classificação anterior à
> correção de qualificador e ao ajuste de train/serve skew. Os números de
> SANEADO e REVISAO vão mudar; os de junção devem subir.

### Modelo BERT

| Métrica | Valor |
|---|---|
| F1 por token (tokens de atributo) | **0,985** |
| Precisão | **1,000** |
| Recall | 0,969 |
| Sequência 100% correta | **0,886** |
| Tempo de treino (CPU, 4 threads) | 40 min |
| Tamanho | 518 MB |
| Exemplos de treino | 10.359 (61.869 anotações, nenhuma anotada à mão) |

### LLM no Bedrock

| | |
|---|---|
| Modelo para volume | `us.anthropic.claude-haiku-4-5-20251001-v1:0` |
| Modelo para casos difíceis | `us.anthropic.claude-sonnet-5` |
| Custo estimado (3.569 registros escalados) | **~US$ 11** |
| Com prompt caching agrupado por classe | ~US$ 5,50 |
| Status | validado em 3 casos de teste; **ainda não rodou na base** |

---

## 3. O que existe

### Código

```
src/saneamento/
  texto.py          normalizacao, conversao de unidade (psi->bar, DN->POL), M12X50
  pdm.py            le o PDM da planilha; decide atributo condicional
  caixas.py         a caixa, seu tipo (TEXTUAL/NUMERICA/LIVRE) e as bandas
  regras.py         camada 1: sujeito, gazetteer, gramatica, sinonimo, aprendido
  sinonimos.py      camada 2: conhecimento de dominio curado
  aprendizado.py    camada 3: dicionario alimentado por LLM e BERT
  bert.py           camada 4: recorte BIO, treino com checkpoint e retomada
  embeddings.py     camada 5: similaridade com margem e trava de gemeo numerico
  arbitro.py        mede discordancia entre camadas e decide se escala
  llm.py            camada 6: Claude no Bedrock, so no residuo
  validador.py      O PORTAO: invariantes do PDM; monta a chave de identidade
  encaixotador.py   monta a grade de caixas de uma linha
  pipeline.py       orquestra
  dados.py          leitura das planilhas
```

### Scripts

| Script | O que faz |
|---|---|
| `00_ver_classe.py` | mostra as caixas que o PDM define para uma classe |
| `01_compilar_pdm.py` | planilha do PDM → `artefatos/pdm.json` |
| `02_gerar_rotulos.py` | distant supervision → dataset de treino |
| `03_treinar_bert.py` | treina o recortador (`--retomar` continua) |
| `04_extrair.py` | pipeline completo nos 23.554 registros |
| `05_encaixotar.py` | imprime a grade de caixas (`--ver 12711820`) |
| `06_juntar.py` | agrupa por chave e escolhe o sobrevivente |
| `07_catalogo.py` | gera o xlsx final |
| `08_auditar_pdm.py` | enumera os riscos estruturais do PDM |
| `rodar_tudo.sh` | a cadeia inteira |

### Artefatos gerados

| Arquivo | Conteúdo |
|---|---|
| `artefatos/catalogo_final.xlsx` | **o entregável**: 49 abas, uma por classe, características em colunas |
| `artefatos/plano_juncao.csv` | código, ação, `USAR <código>`, estoque consolidado |
| `artefatos/saneado_base.csv` | um registro por linha, com descrição no padrão |
| `artefatos/decisoes_base.jsonl` | trilha de auditoria: cada caixa, fonte, banda, motivo |
| `artefatos/caixas_base.jsonl` | a grade de caixas por linha |
| `artefatos/aprendizado.json` | dicionário aprendido, persistente |
| `artefatos/modelo_bert/` | o modelo treinado (não versionado) |

### Documentos

| Documento | Para quem |
|---|---|
| `00-estado-do-projeto.md` | este arquivo: índice e status |
| `01-dados.md` | os 3 xlsx e o PDF, com os problemas medidos |
| `02-plano-projeto.md` | o plano original e a stack |
| `03-treinar-bert.md` | handoff para treinar em outra máquina |
| **`04-como-funciona.md`** | **a explicação didática do pipeline, do zero** |
| `05-riscos-pdm.md` | gerado: os riscos estruturais do PDM |

### Testes

```bash
.venv/bin/python -m pytest tests/ -q     # 73 testes
```

Cobrem as invariantes do PDM (formato de unidade, lista de valores, chave de
identidade), os dois casos do briefing (rolamento 6205 que **deve** juntar,
filtro intercambiável que **não** deve) e uma regressão para cada bug da
seção 5.

---

## 4. Como rodar

```bash
# ambiente (Python 3.12; torch nao tem wheel para 3.14)
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python --index-strategy unsafe-best-match \
  --extra-index-url https://download.pytorch.org/whl/cpu \
  torch transformers numpy scikit-learn openpyxl boto3 pytest

# a cadeia inteira
./scripts/rodar_tudo.sh --treinar --com-llm     # do zero, ~1h
./scripts/rodar_tudo.sh                         # reaproveita o modelo, sem LLM
./scripts/rodar_tudo.sh --rapido                # 3.000 registros, para testar mudanca
```

Inspeções úteis:

```bash
.venv/bin/python scripts/00_ver_classe.py "parafuso sextavado"   # as caixas da classe
.venv/bin/python scripts/05_encaixotar.py --ver 12711820         # a grade de um registro
.venv/bin/python scripts/08_auditar_pdm.py                       # riscos do PDM
```

---

## 5. Bugs encontrados e corrigidos

Esta seção existe porque a banca vai perguntar como sabemos que o resultado está
certo. Nove bugs, e quatro deles inflavam números que já tinham sido reportados.

| Bug | Efeito medido |
|---|---|
| Dicionário de sinônimos nunca ligado no caminho principal (só o `Encaixotador` o consultava) | SANEADO +5,1 pontos ao ligar |
| Cache de sinônimos indexado só pelo nome do atributo, e os 93 nomes do PDM são globais | o `TIPO` de uma classe envenenava o de todas as outras |
| Chave de identidade ignorava os 19 atributos obrigatórios **condicionais** | **534 junções falsas** (1.410 → 876) |
| Validador testava formato `POL` antes de `MM` num atributo que cita os dois | reescrevia `75MM` como `75POL`, trocando a medida |
| Regex de inteiro capturava dígito de dentro de unidade | `SECAO 35MM2` virava `NUMERO CONDUTORES = 35` |
| Qualificador casado como string contígua | 325 mangueiras montadas classificadas como avulsas |
| `temperature` enviado a modelos que o rejeitam | 100% das chamadas ao LLM falhariam |
| Erro do LLM ignorado pelo pipeline | falha total apareceria como "rodou e não achou nada" |
| Train/serve skew: o treino apaga os nomes de atributo, a inferência não | 3.141 registros com `FABRICANTE` etiquetado como valor de `MATERIAL` |

Os três primeiros só apareceram porque fomos buscar um exemplo de junção para o
documento didático e o exemplo estava errado — três cabos idênticos exceto pela
cor (VERDE, AZUL, PRETO) estavam sendo unificados.

**Os números reportados antes das 12h de 2026-11-07 estavam inflados.**

---

## 6. Decisões de arquitetura, e a medição que as sustenta

### O LLM não é a primeira camada

Mais de 90% das caixas são preenchidas por regra determinística: 68% por
casamento literal na lista do PDM, 17% por gramática de grandeza, 8% pela regra
2 do PDM (`M12X50` → bitola + comprimento). Rodar LLM nisso seria substituir o
certo e reproduzível pelo caro e incerto.

### O embedding não decide valor nem classe

Medido no vocabulário do próprio PDM:

```
cos(ACO INOX 304, ACO INOX 316)                     = 0,963
cos(ROSCA NPT,    ROSCA BSP)                        = 0,965
cos(DIN 931,      DIN 933)                          = 0,959
cos(MANGUEIRA HIDRAULICA, MANGUEIRA HIDR. MONTADA)  = 0,975
937 de 946 pares de classes acima de 0,85
```

Os pares que mais precisamos separar são os menos separáveis, porque o PDM
nomeia as coisas com diferenças mínimas e o embedding faz média sobre a frase,
diluindo a palavra discriminante. Em 500 registros, o embedding **nunca** chegou
na banda que dispensa o LLM: todas as 71 propostas caíram na banda do meio, e a
maioria era ruído (`VER DESENHO` → `VEICULO LEVE`).

### O que decide a classe é a evidência de caixa, não a semelhança de nome

`PDM011` é `PDM010` mais `COMPRIMENTO`, `TERMINAL A`, `TERMINAL B` e
`MATERIAL TERMINAIS`. Quando o texto evidencia essas caixas exclusivas, a classe
específica é escolhida — mesmo sem a palavra "MONTADA". Erro: 325 → 43.

### Duplicidade é igualdade de chave, não similaridade

Depois que as caixas estão padronizadas, dois registros são o mesmo item quando
a chave coincide. A justificativa cabe em uma frase que suprimentos entende:
*"são o mesmo item porque todos os atributos obrigatórios coincidem"*. Nenhum
modelo opina. Nos 15 produtos reais da base: **zero junções indevidas**, com a
regra 13 respeitada (filtros intercambiáveis não foram unificados).

### Dado ausente não vai para o LLM

33% dos atributos obrigatórios estão genuinamente ausentes do texto. O teto do
LLM em SANEADO é **+3,2 pontos** (760 registros de conflito puro). Os outros
14.158 em PENDENTE precisam de enriquecimento (catálogo de fabricante, norma),
não de extração — e qualquer modelo que preencha ali está inventando.

---

## 7. O que falta

Em ordem de retorno por esforço:

| # | O que | Por que importa |
|---|---|---|
| 1 | **Extração em duas passadas** para atributos condicionais | trava `PDM062` (disjuntor, 354 registros) em 0%: `CORRENTE NOMINAL` e `CURVA` só se aplicam depois de saber o `TIPO`, mas a extração decide as caixas antes. O dado está no texto (`IN 25A CURVA C`) e nunca é lido |
| 2 | **Fechar lacunas de substantivo** nos 718 `FORA_DO_PDM` | `O-RING`→`ANEL O-RING`, `CONTACTOR`→`CONTATOR`, `JOELHO`→`COTOVELO`, `TAMPAO`→`CAP`, `BOTINA`→`CALCADO SEGURANCA`. Entradas de dicionário, determinísticas |
| 3 | **Rodar o LLM** nos registros escalados | mede o ganho real e alimenta o dicionário aprendido pela primeira vez (~US$ 11) |
| 4 | **Retreinar o BERT** com as duas variantes de texto (com e sem rótulo, marcando o rótulo como `O`) | corrige o train/serve skew na origem, em vez de filtrar na inferência |
| 5 | **Processar os 520 pedidos** de cadastro | o fluxo de entrada: `APROVADO` / `JA_EXISTE` / `DEVOLVIDO` / `FORA_DO_PDM`. É o slide do pitch |
| 6 | **Enriquecimento** com fonte registrada | único caminho para os 14.158 em PENDENTE |
| 7 | **Interface** (Streamlit) | diagnóstico, antes/depois, clusters, fila de revisão, simulador de pedido |

Pendências menores:

- `sinonimos.py` tem entradas que a camada de abreviação já cobre; vale encolher.
- Há três `.xlsx` duplicados na raiz, iguais aos de `dados/`.
- Nada de `artefatos/` está versionado (`.gitignore`); os `.jsonl` de treino
  (2,7 MB) talvez devam entrar, para o treino em outra máquina ser um `git clone`.
- Migrar o cliente Bedrock de `boto3` para o SDK da Anthropic destravaria prompt
  caching com menos atrito (cairia de ~US$ 11 para ~US$ 5,50).

---

## 8. Glossário rápido

| Termo | Significado |
|---|---|
| **PDM** | Padrão Descritivo de Materiais: o documento da empresa que define o cadastro correto |
| **Caixa** | um atributo de um item; a célula da grade |
| **Grade** | todas as caixas de uma linha |
| **Sujeito** | `SUBSTANTIVO + QUALIFICADOR` da classe (`PARAFUSO SEXTAVADO`) |
| **Chave de identidade** | concatenação das caixas obrigatórias; mesma chave = mesmo item |
| **Banda** | nível de confiança da caixa; define se chama o LLM |
| **Margem** | distância entre o 1º e o 2º valor mais parecido; o que autoriza aceitar |
| **Sobra** | texto que nenhuma caixa reivindicou; diagnóstico de recorte |
| **Distant supervision** | treinar com rótulos tirados dos próprios dados, sem anotação manual |
