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

## Abrir a aplicação

```bash
git clone https://github.com/Igor-Roberto-Alves/vxwinners.git
cd vxwinners && ./rodar.sh
```

É só isso. O script prepara o ambiente, treina os modelos de sugestão e monta o banco
(um PostgreSQL embutido, nada para instalar) na primeira vez, sobe a API e abre
`http://localhost:8000/`. Da segunda em diante, segundos.

**O que você precisa ter:** Python 3.12 e rede na primeira execução, para o `pip`. Nada mais —
os dados vêm no repositório. `Ctrl+C` encerra.

Se o `python3.12 -m venv` da sua distribuição vier sem `pip` (Debian e Ubuntu sem o pacote
`python3.12-venv`), o script detecta e usa o [`uv`](https://docs.astral.sh/uv/) se houver; se não
houver, ele diz qual dos dois instalar e para.

Comece em **Buscar material**, ou assuma um pedido em **Pedidos de cadastro**. Para decidir
exceções, troque o usuário no topo para `bia · revisora` — quem pede a exceção não pode decidi-la.
Detalhes, variações do comando e as outras telas em [Aplicação](#aplicação).

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

**3. Backend do modo de cadastro** — [`backend/`](backend/README.md)

FastAPI e PostgreSQL. Estrutura a base inteira (classe em 99,5% e chave de identidade fechada em 78,2%
dos 23.554 registros), acha 3.314 códigos redundantes (R$ 19,27 mi em estoque, ainda sem revisão do
time) e conduz o cadastro do pedido à aprovação, com exceções, segundo analista, auditoria imutável e
envio ao ERP. Os modelos do serviço de sugestão rodam dentro dele, em `/sugestao`.
Plano, decisões e medições: [`docs/06-plano-modo-cadastro.md`](docs/06-plano-modo-cadastro.md).

**4. Interface, ligada à API** — [`plataforma.html`](plataforma.html) + [`backend/app/painel/`](backend/app/painel/index.html)

O frontend do time é a moldura, e a tela de cadastro é o painel, embutido nela: três colunas, com a busca e os pedidos
à esquerda, o formulário no meio e, à direita, a descrição, os itens parecidos e a decisão. A etiqueta no topo diz se a
tela usa **dados reais** ou é **demonstração**.

- **Reais:** Buscar material, Cadastrar novo item, Pedidos de cadastro, Cadastros, Revisão de exceções,
  **Fila de intervenção**, **Radar**, **Códigos juntados e NCM trocado** e **Interferência de IA** (as
  quatro últimas leem a saída do pipeline, não a API — a etiqueta do topo diz `saída do pipeline`).
- **Demonstração:** Início, Requisições e Base.

**Radar** passou a sair de `artefatos/radar.json` (`scripts/20_radar.py`), e cada número leva a própria
procedência: `medido` quando sai de um artefato ou de um gabarito, `estimado` quando é cálculo sobre a
base, `premissa` quando é parâmetro ajustável, e **`não medido`** quando não existe medição — nesse caso
a tela diz isso em vez de mostrar um número. Capital consolidável R$ 30,24 mi (15,1% dos R$ 200,87 mi em
estoque, mesma definição do `valor_financeiro.md`, com a precisão de junção 98,5% medida no gabarito);
capital já consolidado R$ 0,00, porque nenhuma unificação foi executada no ERP; e um cartão de eficácia
com precisão, cobertura, invenção, classe, junção e determinismo, cada linha apontando o arquivo de onde
veio.

```bash
uv run --no-project --with pandas --with openpyxl python scripts/20_radar.py
```

**Fila de intervenção** é onde o saneamento pede ajuda. Cada campo que ficou vazio chega classificado
pela ação que pede, e não pelo erro que é: `confirmar` quando o valor já está decidido (o texto trazia
e a leitura perdeu, ou há candidato acima de 90%), `escolher` quando há candidatos com probabilidade e
suporte, `sem pista` quando o texto traz algo fora do padrão e nada se sustenta, e `fonte externa`
quando o texto não traz o dado — esse último sai da fila, porque não é trabalho de leitura. Hoje são
3.482 itens, 1.478 campos de um clique e R$ 10,84 mi de capital em risco na fila. A ordem é pelo que dá
para resolver e, dentro de cada grupo, pelo capital. As decisões saem em `.jsonl` no formato que o
pipeline consome de volta.

```bash
uv run --no-project --with pandas --with openpyxl python scripts/19_fila_intervencao.py
```

**Códigos juntados e NCM trocado** abre o que antes só existia somado no Radar. Até aqui a tela de
clusters mostrava sete grupos escritos à mão dentro do `plataforma.html`, com confiança inventada por
grupo, enquanto o Radar dizia "1.991 grupos" e "1.104 NCM corrigidos" sem que houvesse onde conferir
nenhum dos dois. Agora são duas abas, as duas completas:

- **Códigos juntados** — os 1.991 grupos de identidade. Em cada um, o código que **fica** em verde e os
  que **saem** riscados, com saldo somado, capital liberado, centros e o que diverge entre eles (NCM,
  unidade, saldo no código que sai, LLM na chave). Clicar na linha abre as **linhas originais da
  base**, uma por código, com as colunas do ERP — incluindo data de criação e última movimentação, que
  é o que de fato decide qual código fica — e, abaixo, a mesma informação virada em comparação campo a
  campo contra o código que fica. O rádio no cabeçalho troca quem fica e a troca vai na decisão
  exportada. Não há percentual de confiança por grupo porque o pipeline não produz um: no lugar dele, a
  precisão da junção medida no gabarito (98,5%), que vale para o conjunto.
- **NCM trocado** — toda alteração de NCM com o valor antigo riscado ao lado do novo, separada pelo que
  a mudança significa: **1.104 trocados** (dígitos diferentes — muda a tributação e exige o tributário,
  R$ 2,94 mi em estoque), **597 preenchidos** (entraram vazios, derivados da classe), **8.063
  reformatados** (mesmos dígitos, só a pontuação; publicados por amostra de maior capital, com a
  contagem total ao lado) e **611 que continuam sem NCM**, porque a classe tem NCM condicional.

```bash
uv run --no-project --with pandas --with openpyxl python scripts/21_juncao_ncm.py
```

**Interferência de IA** é a tela que torna o dicionário aprendido auditável. Ele é a camada mais barata
do pipeline (`11_canonizar_termos.py` resolve 1.963 termos por US$ 0,68 em vez de 11.852 registros por
US$ 44,60) e por isso a mais perigosa: uma pergunta respondida uma vez vira regra e decide sozinha em
centenas de registros. São **487 regras**, **251** delas decidindo **4.819 linhas** e **R$ 20,37 mi** em
estoque. Cada regra traz:

- **a procedência**, rotulada: `registrada` quando o dicionário gravou o código de origem, `desempate`
  quando a linha está em `desempate_llm.jsonl`, `derivada` quando é a linha mais antiga em que a regra
  vale hoje — pista, não registro, e a tela diz isso. Até aqui o `aprendizado.json` **não guardava**
  a linha de origem; `Entrada.origens` foi acrescentado e os quatro pontos que alimentam o dicionário
  (`arbitro.incorporar_llm`, `pipeline._aprender_do_bert`, `10_desempatar_llm.py` e
  `11_canonizar_termos.py`) passaram a informar o código. Daqui em diante é registro.
- **todas as linhas em que decidiu**, cada uma com **o trecho do texto que a regra leu**, com o termo
  destacado — a descrição curta do ERP tem 40 caracteres e corta justo o termo, o que faz aplicação
  legítima parecer palpite.
- **o que a regra acrescentou ao texto**: 317 regras gravam palavra que o termo não traz, em 3.743
  linhas e R$ 14,75 mi. `ACO CARBONO → ACO CARBONO ZINCADO` acrescenta o zincado em 245 linhas; a regra
  irmã `ACO ZINCADO → ACO CARBONO ZINCADO` acrescenta a liga em outras 255. Pode ser escolha forçada
  pela lista do PDM ou palpite — a tela mostra, a revisão decide.

**Derrubar não é por linha.** Marcar "não valeu aqui" abre a pergunta com as outras linhas da mesma
regra e o capital que elas carregam: *não valeu só nesta linha* (a regra segue, aquele registro vira
exceção) ou *a regra não vale* (cai, e todas as linhas que ela decidiu voltam para revisão, listadas na
hora). As decisões saem em `.jsonl` no formato de `aprendido_sugestoes.jsonl`, que o
`18_curar_aprendizado.py` consome.

```bash
uv run --no-project --with pandas --with openpyxl python scripts/22_regras_ia.py
```

Três decisões de projeto:

- **Sugestão não preenche campo sozinha.** Nada vindo do histórico ou dos modelos entra sem um clique. Gravar um part
  number errado funde itens distintos na mesma chave de identidade (regra 10 do PDM): `ASME B16.11` sugere `B1611` a 45%.
- **"Já existe" vem dos atributos, não da semelhança de texto.** Nos 15 produtos reais da análise de mercado, comparar
  texto não achou nenhum duplicado.
- **Classe é sempre confirmada por uma pessoa.** A lida do pedido entra como proposta e bloqueia a aprovação até alguém
  confirmar. O que nada no PDM reconhece pode ser recusado.

A interface precisa do servidor: aberta sozinha, ela avisa que a API está fora do ar.

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

**Dependências:** [`backend/requirements.txt`](backend/requirements.txt), com versões fixadas.

```bash
python3.12 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt
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

### Aplicação

Um comando sobe tudo: prepara o ambiente, os modelos e o banco na primeira vez, e abre a interface.

```bash
./rodar.sh                 # abre http://localhost:8000/
./rodar.sh --sem-navegador
PORTA=8100 ./rodar.sh
```

Comece em **Buscar material**, digitando o nome do item, ou abra um pedido em **Pedidos de cadastro**. Para decidir exceções, troque o usuário no topo para
`bia · revisora`: quem pediu a exceção não pode decidi-la.

Sem a etapa de LLM, a base fica só com a leitura por regras. Para a leitura completa (~17 min, ~US$ 40) e
os demais comandos, veja [`backend/README.md`](backend/README.md). Rotas: `http://localhost:8000/docs`.

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
backend/                    API, banco, estruturação da base, cadastro, testes
frontend/                   cadastro real, fila de intervenção, junção/NCM, tema e teste de ponta a ponta
  cadastro.js intervencao.js juncao.js regras_ia.js radar.js
  dados/{fila_intervencao,juncao_ncm,regras_ia,radar}.json
src/saneamento/             pipeline de saneamento (caixas, BERT, junção, catálogo)
plataforma.html      casca da interface
rodar.sh                    sobe tudo
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

**2. Benchmark não roda em clone limpo sem `00_prep.py`.** Os splits são regeneráveis e
determinísticos (`SEED = 42`), mas não versionados — então `pred/` e `benchmark.csv` commitados não
podem ser reauditados antes de regenerar os splits.

**3. Os 363 grupos suspeitos não foram verificados um por um.** São a saída de um modelo discordando
do rótulo com confiança alta; as amostras inspecionadas estão certas, mas a lista inteira ainda
precisa de revisão humana antes de virar correção na base.

**4. A interface ainda tem telas de demonstração.** Início, Requisições e Base usam dados
embutidos no arquivo. A autenticação é só de desenvolvimento, e o usuário é
escolhido no topo da tela: não use em produção. Limites completos em [`backend/README.md`](backend/README.md).
