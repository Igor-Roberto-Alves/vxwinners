# vxwinners — Cadastro e saneamento de materiais

Hackathon VX · **Desafio 01**. Empresa fictícia *Serra Azul Mineração e Energia*: seis plantas,
**23.554 materiais cadastrados**, 22 anos de deriva e um padrão descritivo (PDM) que 79% da base
não cumpre.

O problema tem três frentes — **sanear** a base que existe, **padronizar** o que está chegando e
**enriquecer** o que falta. Este repositório ataca a lacuna que viabiliza as três: **preencher os
campos que estão vazios**.

| Campo | Vazios na base | % |
|---|---:|---:|
| `REFERENCIA_FABRICANTE` | 18.488 | 78,5% |
| `FABRICANTE` | 15.674 | 66,5% |
| `NCM` | 1.173 | 5,0% |
| `GRUPO_MERCADORIA` | 0 | — |

Sem fabricante e sem part number, a chave de identidade que o PDM define para sobressalentes e
filtros (regra 10) é **impossível de calcular** — e é exatamente nessas classes que está **84% do
valor do estoque**. Preencher esses campos é o que destrava a deduplicação.

---

## O que está pronto

**1. Benchmark auditado de 10 soluções × 4 campos** — [`preenchimento/`](preenchimento/)

Avaliação por mascaramento: linhas onde o campo *está* preenchido viram treino/teste, e o valor
conhecido é o gabarito. O split de teste é **congelado** e idêntico para todas as soluções
(2.000 linhas por campo; 1.500 para referência).

As 10 soluções, de graça a caríssima: `prior` (baseline), `regras` (determinística),
`tfidf_lr` (ML clássico), `knn_cohere` (embeddings Bedrock), `llm_fewshot_{haiku,sonnet,fable}`
(vocabulário candidato + 3 exemplos + saída JSON, lotes de 20) e
`llm_naive_{haiku,sonnet,fable}` (registro cru, sem vocabulário, sem exemplos — o comparador).

**2. Preenchimento dos faltantes reais** — [`preenchimento/08_preencher.py`](preenchimento/08_preencher.py)

Os vencedores do benchmark aplicados aos vazios de verdade, com `metodo`, `conf` e `top3` por linha
em [`preenchimento/saida/`](preenchimento/saida/). Roda em **32 segundos** (o custo de LLM foi pago
uma vez; reexecução resolve tudo do checkpoint).

| Campo | Vazios | Resultado | Método |
|---|---:|---|---|
| `NCM` | 1.173 | **1.173 preenchidos**, confiança média 0,85 | `tfidf_lr` · custo zero |
| `FABRICANTE` | 15.674 | **15.674 preenchidos**, zero pendência | 2.765 por léxico + 12.909 por Sonnet few-shot · $20,45 |
| `REFERENCIA_FABRICANTE` | 18.488 | 7.728 extraídas · **10.760 pendentes** | extração por regras, confiança por origem |
| `GRUPO_MERCADORIA` | 0 | **363 rótulos suspeitos** | bônus: modelo discorda com conf ≥ 0,90 |

A extração de referência é **estratificada por confiança**, e isso importa mais que a média:

| Origem | Linhas | Conf | Leitura |
|---|---:|---:|---|
| `marcador` (`REF:`, `PN:`, `COD:`) | 3.364 | 0,85 | confiável |
| `perto_fab` (adjacente ao fabricante) | 572 | 0,60 | confiável |
| `mais_longo` (candidato mais longo) | 3.792 | 0,45 | **melhor esforço — ver limitações** |
| `pendente` (sem candidato) | 10.760 | — | abstenção explícita |

**Os 363 grupos suspeitos são um achado à parte:** são erros de classificação que já estavam na
base. Um contraeixo de britador cônico cadastrado como `FIL01` (filtros) quando é `SOB01`; um anel
O-ring como `ELE01` quando é `VED01`; uma porca autotravante como `TRA01` quando é `FIX01`. Lista
completa em [`saida/grupo_suspeitos.csv`](preenchimento/saida/grupo_suspeitos.csv); contagens em
[`saida/resumo_preenchimento.json`](preenchimento/saida/resumo_preenchimento.json).

**3. API de sugestão de cadastro** — [`servico/api.py`](servico/api.py)

FastAPI na porta 8700. Recebe a descrição em texto livre e devolve, numa chamada, sugestão de grupo,
NCM, fabricante, referência **e a lista de materiais similares já cadastrados** — o anti-duplicata na
porta de entrada.

**4. Interface, ligada à API** — [`mockup_plataforma.html`](mockup_plataforma.html)

Catálogo MRO navegável, com duas telas ligadas ao serviço:

- **Cadastro de item** → `POST /sugerir`. O texto livre do pedido entra (analisado ao digitar, ~20 ms)
  e a tela devolve grupo, NCM, fabricante, referência e os itens parecidos já cadastrados. Cada
  sugestão vem com **chips clicáveis** — aplica-se um valor por vez, ou todos de uma vez pelo botão.
  Os **quatro estados** do fluxo (`APROVADO`, `JÁ EXISTE`, `DEVOLVIDO`, pendências) saem no envio.
- **Busca de materiais** → `POST /similares`. A consulta passa a buscar por similaridade na base
  inteira, substituindo os cards estáticos pelos resultados reais marcados `via API`.

Duas decisões de projeto na ligação, ambas vindas do que o benchmark mostrou:

- **Sugestão fraca não preenche campo sozinha.** O corte é `conf ≥ 0,60`. Abaixo disso o campo fica
  vazio e marcado como pendência, com o motivo escrito na tela; o chip aparece tracejado e, se o
  usuário clicar nele, o valor entra marcado como `manual`, não como sugestão da IA. Isso existe
  porque gravar um part number errado funde itens distintos na mesma chave de identidade (regra 10
  do PDM) — duplicata falsa é pior que campo vazio. Na prática: `ASME B16.11` sugere `B1611` a 45% e
  **não é aplicado**; fabricante vindo do modelo (não do texto) a 4% também não.
- **Trava de duplicidade antes de criar código.** Similaridade ≥ 85% exibe o banner `JÁ EXISTE` com
  o código a usar; entre 60% e 85%, pede confirmação.

A página **continua funcionando com o serviço desligado** — detecta a ausência, avisa e mantém o
comportamento de mockup, para poder ser aberta sozinha.

---

## Resultados

Acurácia top-1 no split de teste congelado. **Negrito = vencedor do campo.**

| Solução | Grupo | NCM | Fabricante | Referência | Custo (teste) |
|---|---:|---:|---:|---:|---:|
| `regras` | 96,2% | 46,9% | 73,9%¹ | **84,4%** | **$0** |
| `tfidf_lr` | 96,5% | **91,1%** | 82,2% | 6,1% | **$0** |
| `knn_cohere` | **96,6%** | 90,2% | 80,9% | 9,5% | $0,24 |
| `llm_fewshot_haiku` | 96,5% | 88,7% | 83,3% | 81,1% | $4,92 |
| `llm_fewshot_sonnet` | **96,6%** | 87,3% | **84,3%** | 81,2% | $15,26 |
| `llm_fewshot_fable` | 96,5% | 90,4% | 84,1% | 82,6% | $69,54 |
| `llm_naive_haiku` | 0,0% | 2,6% | 75,1% | 78,7% | $3,44 |
| `llm_naive_sonnet` | 0,0% | 42,7% | 78,1% | 80,6% | $8,00 |
| `llm_naive_fable` | 0,0% | 76,7% | 79,4% | 79,7% | $72,22 |
| `prior` | 32,4% | 46,9% | 16,2% | 0,0% | $0 |

¹ `regras` abstém em 26% dos casos; **nos que cobre, acerta 99,9%** — é precisão, não cobertura.

Benchmark completo (cobertura, top-3, F1 macro, tokens, segundos, custo por campo):
[`preenchimento/benchmark.csv`](preenchimento/benchmark.csv).
Custo total de execução: **$173,62** · 1,7 h de processamento.

### As duas conclusões

**1. Engenharia de prompt vale mais que modelo maior.** Em `GRUPO_MERCADORIA`, as três LLMs ingênuas
acertam **0,0%** — um modelo que não recebe o vocabulário não tem como adivinhar que o rótulo é
`SOB01` e não "sobressalentes". A mesma família de modelos, recebendo a lista de valores válidos e
três exemplos, chega a 96,6%. **O ganho está na lista fechada, não no modelo.** Confirmação: em NCM,
`llm_naive_haiku` faz 2,6% e `llm_fewshot_haiku` faz 88,7%.

**2. O vencedor é quase sempre o mais barato.** `tfidf_lr` ganha NCM (91,1% top-1, 98,9% top-3) com
custo zero e 3 minutos. `regras` ganha referência — porque part number é problema de **extração**,
não de classificação, e é por isso que `tfidf_lr` e `knn_cohere` desabam para 6% e 9,5% nesse campo.
A LLM só vale onde nada determinístico alcança: fabricante quando o nome não está escrito no texto.

Daí a cascata usada no preenchimento real: **regras primeiro, LLM só no resto.** Em `FABRICANTE`,
2.765 dos 15.674 saíram do léxico a custo zero; os 12.909 restantes foram para o Sonnet few-shot.

---

## Como rodar

**Dependências** (não há `requirements.txt` ainda — ver limitações):

```bash
pip install pandas numpy scikit-learn scipy joblib openpyxl boto3 fastapi uvicorn pydantic
```

As soluções `knn_cohere`, `llm_fewshot_*` e `llm_naive_*` exigem **AWS Bedrock** em `us-east-1`
com acesso aos modelos listados em [`preenchimento/bedrock_util.py`](preenchimento/bedrock_util.py).
As demais (`prior`, `regras`, `tfidf_lr`) rodam offline.

### Benchmark

```bash
cd preenchimento
python 00_prep.py            # converte o xlsx e CONGELA os splits (rode primeiro)
python 01_prior.py
python 02_regras.py
python 03_tfidf.py
python 04_knn_embeddings.py  # Bedrock · embeddings cacheados em cache/
python 05_llm_fewshot.py --tudo
python 06_llm_naive.py --tudo
python 07_benchmark.py       # recomputa as métricas só a partir de pred/*.csv
python verif_sanidade.py     # auditoria dos splits e das predições
python verif_metricas.py     # reconfere o benchmark.csv de forma independente
```

`07_benchmark.py` **nunca confia na métrica calculada pela própria solução** — recomputa tudo dos
arquivos de predição. Os dois verificadores são independentes do benchmark e saem com código 1 em
qualquer violação; o relatório fica em
[`preenchimento/metricas/verificacao_metricas.json`](preenchimento/metricas/verificacao_metricas.json),
com as divergências conhecidas registradas em `_anomalias`.

Os scripts aceitam modo de validação barato antes da execução completa:

```bash
python 03_tfidf.py --amostra 500
python 04_knn_embeddings.py --valida
python 05_llm_fewshot.py --validar
```

### Preenchimento dos faltantes

```bash
cd preenchimento && python 08_preencher.py
```

### API e mockup

Um comando sobe tudo — prepara os dados, treina (só na primeira vez), sobe API e interface:

```bash
./rodar.sh                 # abre http://127.0.0.1:8080/mockup_plataforma.html
./rodar.sh --sem-navegador
```

Vá em **Cadastro de item** na barra lateral. O indicador no cartão "Origem do pedido" mostra se o
serviço foi encontrado; *Usar outro exemplo* percorre sete pedidos reais do desafio, incluindo os
casos difíceis (part number fraco, catálogo em inglês, item fora do PDM).

Passo a passo, se preferir:

```bash
cd preenchimento && python 00_prep.py    # gera dados/base.csv, de que o treino depende
cd ../servico && python treina.py        # ~3 min
python -m uvicorn api:app --host 127.0.0.1 --port 8700
bash exemplos_curl.sh                    # chamadas de exemplo
cd .. && python3 -m http.server 8080 --bind 127.0.0.1
```

Servir por HTTP é preferível a abrir o arquivo direto. Via `file://` a origem é `null`, e a
integração só sobrevive porque a API declara `allow_credentials=False` com `allow_origins=["*"]` —
mudar isso quebra o acesso por arquivo, mas não o acesso por localhost.

```
GET  /saude      status e modelos carregados
POST /sugerir    {"descricao": "...", "grupo": null}  -> grupo, ncm, fabricante, referência, similares
POST /similares  {"descricao": "..."}                 -> só os similares
```

---

## Estrutura

```
dados/                      os 3 xlsx do desafio (base, pedidos, PDM)
docs/
  01-dados.md               anatomia dos dados e problemas medidos
  02-plano-projeto.md       arquitetura do pipeline de saneamento
preenchimento/
  contrato.py               splits, normalização e formato de predição — o contrato comum
  00_prep.py                prepara e congela os splits
  01..06_*.py               as 10 soluções
  07_benchmark.py           agrega e recomputa as métricas
  08_preencher.py           aplica os vencedores aos faltantes reais
  verif_{sanidade,metricas}.py   auditoria independente
  bedrock_util.py           Bedrock com retry/backoff e contagem de custo
  benchmark.csv             o resultado do benchmark
  pred/ metricas/           predições por solução e métricas auditadas
  saida/                    preenchido_{NCM,FABRICANTE,REFERENCIA_FABRICANTE}.csv
                            grupo_suspeitos.csv · resumo_preenchimento.json
servico/
  treina.py api.py exemplos_curl.sh
mockup_plataforma.html
Hackathon_VX_Desafio01_Cadastro_e_Saneamento.pdf
```

Não versionados (`.gitignore`): `preenchimento/dados/` e `preenchimento/cache/` (splits e
embeddings, regeneráveis) e `servico/modelos/` (artefatos de treino).

---

## Limitações conhecidas

**1. A faixa `mais_longo` da extração de referência tem muito falso positivo.** São 3.792 das 7.728
extrações (49%), e a inspeção mostra que a regra do "candidato mais longo" está capturando **norma
técnica e especificação de material** como se fossem part number:

| `y_pred` | Linhas | O que realmente é |
|---|---:|---|
| `B1611` | 531 | norma ASME B16.11 |
| `B1821` | 478 | norma ASME B18.21 |
| `F316` | 298 | grau de material A182 F316 |
| `CF8M` | 229 | grau de material A351 CF8M |
| `B165` | 150 | norma ASME B16.5 |
| `SS304` / `SS316` | 191 | material (aço inox) |

**71% dessa faixa tem 5 caracteres ou menos**, e mais 58 linhas são especificação de rosca
(`UNC78POLX3` = 7/8" UNC × 3"). O caso correto para essas linhas é `PENDENTE`: um item genérico —
`UNIAO DIAM NOMINAL 1.1/4POL, 3000#, MAT ACO CARBONO, ROSCA, ASME B16.11` — simplesmente não tem
part number de fabricante no texto.

**Por que isso é pior que deixar vazio:** `REFERENCIA_FABRICANTE` é metade da chave de identidade
das classes de referência (regra 10 do PDM). Gravar `B1611` em 531 uniões diferentes faz todas elas
colapsarem na **mesma chave** — ou seja, cria duplicata falsa, que é o erro mais caro possível
neste projeto.

As 3.936 linhas de `marcador` e `perto_fab` não têm esse problema. **Recomendação: tratar
`conf = 0,45` como pendência, não como valor** — o que eleva as pendências de 10.760 para ~14.552 e
mantém só o que é confiável.

Os 84,4% do benchmark para `regras` não contradizem isso: foram medidos em linhas onde a referência
*existia* no gabarito. Nos 18.488 campos genuinamente vazios a distribuição é outra — boa parte não
tem part number nenhum a extrair.

**2. Sem `requirements.txt`.** As dependências acima foram levantadas dos imports; não há versões
fixadas.

**3. Benchmark não roda em clone limpo sem `00_prep.py`.** Os splits são regeneráveis e
determinísticos (`SEED = 42`), mas não versionados — então `pred/` e `benchmark.csv` commitados não
podem ser reauditados antes de regenerar os splits.

**4. Os 363 grupos suspeitos não foram verificados um por um.** São a saída de um modelo discordando
do rótulo com confiança alta; as amostras inspecionadas estão certas, mas a lista inteira ainda
precisa de revisão humana antes de virar correção na base.

**5. A análise de mercado está em branch separada.** `docs/03-analise-mercado.md` e `scripts/`
quantificam o custo do problema (R$ 36,6 M endereçáveis, 18,2% do estoque) na branch
`analise-de-mercado` — já publicada em `origin`, ainda não integrada ao `main`.

**6. O estado `FORA_DO_PDM` não é detectado.** O serviço sempre devolve a classe mais provável —
não tem a opção "nenhuma das anteriores". O pedido `"Cadeira de escritório giratória para a sala de
controle"`, que o briefing planta justamente para ser recusado, volta como `SOB01` a 66% de
confiança. A interface só o deixa passar com NCM pendente (30%), o que atenua mas não resolve.
Falta um limiar de rejeição ou uma classe `FORA_DO_PDM` treinada.

**7. Escopo.** Este repositório resolve o **preenchimento de campos** e o **fluxo de entrada**.
A deduplicação em lote por chave de identidade sobre os 23.554 registros e a montagem automática da
descrição PDM a partir dos atributos extraídos estão desenhadas em
[`docs/02-plano-projeto.md`](docs/02-plano-projeto.md), não implementadas — a tela de cadastro monta
a descrição a partir de um schema fixo de 5 classes, não das 44 do PDM.
