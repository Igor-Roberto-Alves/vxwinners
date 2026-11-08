# Plano de validação: execução de ponta a ponta, gabarito de cadastro, checklist do briefing e valor financeiro

Data: 2026-11-07. Roteiro para aplicar, em quatro frentes (V1 a V4). Cada frente
diz o que entra, o que sai, os comandos, quem faz e quando está pronta.

Complementa o gabarito das características, da classe e da junção
(`avaliacao/PROMPT_gabarito_caracteristicas.md`), que é a frente principal e
corre em paralelo.

## Ordem e dependências

```
V1  execução de ponta a ponta + determinismo ──┐
                                               ├──> V4  valor financeiro como faixa
gabarito da junção (prompt das características)┘         (precisa da precisão da junção)

V2  gabarito de unidade, descrição e sobrevivente   (independente; usa os artefatos de V1)
V3  checklist do briefing                           (independente; consolida tudo no fim)
```

V1 vem primeiro: as outras frentes avaliam artefatos, e eles precisam ser
reprodutíveis. V2 e V3 podem correr juntas. V4 só fecha quando a precisão da
junção existir.

## Regras que valem para as quatro frentes

- **LLM só pelo Bedrock** (`src/saneamento/llm.py`, credenciais no `.env`), com
  `--so-contar` antes e confirmação de quem paga.
- **Gabarito independente do pipeline:** para anotar, use o texto cru
  (`dados/01_base_materiais.xlsx`) e o PDM (`dados/03_padrao_cadastro_PDM.xlsx`).
  Os `artefatos/` servem só para **sortear** casos, nunca para rotular.
- **Gabarito feito por LLM tem conferência humana:** uma planilha de revisão com
  as divergências e 10% do resto, preenchida por alguém do time.
- **Cada número sai de um script**, que grava o resultado num `.md` em
  `avaliacao/`. Nenhum número é digitado à mão no pitch.

---

## V1 · Execução de ponta a ponta e teste de determinismo

**Objetivo:** reproduzir todo o resultado a partir de um clone limpo, e provar
que duas execuções com as mesmas entradas dão o mesmo resultado.

### V1.1 Cadeia completa num script só

O `scripts/rodar_tudo.sh` atual para no catálogo e não conhece os passos desta
rodada. Proposta: `scripts/rodar_completo.sh`, com esta ordem:

| # | Passo | Comando | LLM |
|---|---|---|---|
| 0 | testes | `pytest tests -q` | — |
| 1 | compilar o PDM | `01_compilar_pdm.py` | — |
| 2 | rótulos de treino | `02_gerar_rotulos.py` | — |
| 3 | treinar o BERT (opcional) | `03_treinar_bert.py` | — |
| 4 | extração sem LLM | `04_extrair.py --sem-llm` | — |
| 5 | canonizar termos | `11_canonizar_termos.py` | Bedrock |
| 6 | desempate | `10_desempatar_llm.py` | Bedrock |
| 7 | ausente, genérico ou perdido | `12_detectar_ausentes.py --amostra 100000` | Bedrock |
| 8 | extração aplicando 5–7 | `04_extrair.py --sem-llm --aplicar-desempates --aplicar-deteccao` | — |
| 9 | completações sugeridas | `14_sugerir_completacoes.py` | — |
| 10 | junção | `06_juntar.py` | — |
| 11 | catálogo | `07_catalogo.py` | — |
| 12 | avaliações | `evaluate.py`, `evaluate_caracteristicas.py`, `evaluate_cadastro.py` (V2) | — |
| 13 | manifesto | grava `artefatos/manifesto.json` | — |

Opções: `--com-llm` (sem ela, os passos 5–7 reaproveitam os arquivos de resposta
já gravados em `artefatos/`, que são versionados), `--treinar`, `--rapido`
(3.000 registros).

**Manifesto** (`artefatos/manifesto.json`): commit do código, hash SHA-256 do
`pdm.json`, do `aprendizado.json` de entrada, do `config.json` do BERT, do
`desempate_llm.jsonl` e do `deteccao_ausentes.jsonl`, e as contagens finais
(estados, chaves, redundantes, capital). Cada número do pitch aponta para um
manifesto.

### V1.2 Congelar o dicionário aprendido

Hoje o `04_extrair.py` **grava** no `aprendizado.json` durante a execução
(aprende com o BERT e o LLM). Duas execuções seguidas partem de dicionários
diferentes, e o resultado muda. Proposta: opção `--congelar-aprendizado`, que
lê o dicionário mas não grava. O `rodar_completo.sh` usa o modo congelado em
todos os passos menos o 5 (o único que deve ensinar o dicionário).

### V1.3 Teste de determinismo

```bash
# duas execucoes identicas, cada uma com sua copia do dicionario
for v in a b; do mkdir -p /tmp/det_$v; ln -sf $PWD/artefatos/pdm.json /tmp/det_$v/
  ln -sfn $PWD/artefatos/modelo_bert /tmp/det_$v/; cp artefatos/aprendizado.json /tmp/det_$v/
  cp artefatos/desempate_llm.jsonl artefatos/deteccao_ausentes.jsonl /tmp/det_$v/
  .venv/bin/python scripts/04_extrair.py --sem-llm --congelar-aprendizado \
    --aplicar-desempates --aplicar-deteccao --artefatos /tmp/det_$v; done
.venv/bin/python scripts/12_comparar_execucoes.py /tmp/det_a /tmp/det_b
```

**Pronto quando:** o comparador mostra **zero diferenças**, e o mesmo vale para
o `plano_juncao.csv`. Se o BERT der diferença por ponto flutuante entre
execuções, fixar `torch.manual_seed`, `torch.use_deterministic_algorithms(True)`
e 1 thread na inferência, e medir de novo.

### V1.4 Clone limpo

```bash
git clone <repo> /tmp/clone && cd /tmp/clone
uv venv --python 3.12 .venv && uv pip install ... (docs/00, seção 4)
# modelo_bert/ nao e versionado (518 MB): baixar do lugar combinado ou treinar (--treinar, ~40 min)
./scripts/rodar_completo.sh
.venv/bin/python scripts/12_comparar_execucoes.py /tmp/clone/artefatos <repo>/artefatos
```

**Pronto quando:** o clone reproduz os artefatos oficiais com zero diferenças.
Registrar no `docs/00` onde o modelo BERT fica guardado.

**Quem faz:** agente. **Esforço:** baixo (2 a 3 h, com duas execuções de 13 min).

---

## V2 · Gabarito curto de unidade, descrição e sobrevivente

**Objetivo:** medir as três saídas que nenhum gabarito cobre e que mexem
direto no ERP: unidade de medida, descrição no padrão e escolha do código que
fica ativo.

### V2.1 Unidade de medida (60 itens)

| Estrato | Itens | Exemplo | Rótulo esperado |
|---|---|---|---|
| sinônimo | 15 | `UN`, `PCA`, `PÇ` | unidade do PDM (`PC`) |
| embalagem | 20 | `CX`, `JG`, `RL`, `BD`, `GL` | `FILA_FATOR` (não converter sem o fator) |
| incompatível com a classe | 15 | cabo em `PC`, mangueira em `M` quando o PDM pede `PC` | unidade do PDM, com justificativa |
| já correta | 10 | — | a mesma |

Rótulo por item: `unidade_esperada` (ou `FILA_FATOR`), `justificativa`.
Avalia: `UNIDADE_PDM` e `UNIDADE_MOTIVO` do `saneado_base.csv`.
**Erro grave:** converter embalagem sem fator, porque corrompe saldo e preço.
Esse erro é contado à parte.

### V2.2 Descrição no padrão PDM (40 itens)

Rótulo: a descrição que o PDM manda escrever para o item, com os valores do
gabarito das características (assim a descrição não é penalizada duas vezes
pelo mesmo erro de extração). Avalia:
- **igualdade exata** com a `DESCRICAO_PDM`;
- **cada regra do PDM à parte**, por script: começa pelo substantivo e
  qualificador; caixas na ordem da coluna `ORDEM`; sem abreviação (regra 4);
  formato de medida (regra 5); fabricante e referência na descrição só nas
  classes de referência (regras 8 e 9); maiúsculas sem acento (regra 3).

O verificador de regras roda também na **base inteira** (sem gabarito),
como invariante: toda descrição gerada obedece às regras verificáveis.

### V2.3 Sobrevivente e consolidação (30 clusters)

Sorteie 30 clusters do `plano_juncao.csv` (10 de 2 códigos, 10 de 3 a 5, 10
com códigos em centros diferentes). Para cada um, o anotador vê **só as
linhas cruas** (status, completude, última movimentação, estoque, valor,
data de criação) e a regra escrita (ATIVO > completude > movimentação recente
> valor em estoque > mais antigo). Rótulos:
- `sobrevivente_esperado`;
- `estoque_consolidado_esperado`;
- `concorda_com_a_regra` (sim ou não): a pessoa de suprimentos escolheria o
  mesmo? Isso valida a regra, não só a implementação.

### V2.4 Entregáveis

- `avaliacao/20_candidatos_cadastro.py` (sorteio com semente)
- `avaliacao/gold_unidade.csv`, `gold_descricao.csv`, `gold_sobrevivente.csv`
- `avaliacao/evaluate_cadastro.py` → `avaliacao/resultado_cadastro.md`
- `avaliacao/revisao_humana_cadastro.csv`

**Pronto quando:** os três gabaritos existem, foram conferidos por uma pessoa
e o `.md` de resultado foi gerado sobre os artefatos de V1.

**Quem faz:** agente (com o mesmo método e as mesmas regras de independência do
prompt das características) + uma pessoa na conferência (1 h). **Esforço:**
baixo.

---

## V3 · Checklist do briefing

**Objetivo:** cruzar cada exigência do `Hackathon_VX_Desafio01_Cadastro_e_Saneamento.pdf`
com o que existe, onde está e se foi medido.

Os exemplos do briefing (`10293847`, `20384756`, `10482213`, `17730415`,
`24019866`) **não estão na base**: são ilustrativos. Para cada um, o checklist
aponta um **caso equivalente real** da base e mostra o antes e o depois.

### Estado de partida (preencher a coluna "medido" ao aplicar)

| Frente | Exigência do briefing | Onde está hoje | Medido? |
|---|---|---|---|
| Saneamento | juntar duplicidades | `06_juntar.py` → `plano_juncao.csv` (2.687 códigos) | precisão: gabarito da junção |
| Saneamento | um código ativo, os outros bloqueados apontando para ele | `plano_juncao.csv` (`ACAO`, `USAR`) | V2.3 |
| Saneamento | o estoque dos códigos vira um só | `ESTOQUE_CONSOLIDADO` | V2.3 |
| Saneamento | padronizar descrições | `DESCRICAO_PDM` (99,8% no formato) | V2.2 |
| Saneamento | acertar unidade | `validador.unidade` | V2.1 |
| Saneamento | acertar NCM | `NCM_PDM` | sim: 96,6% (gabarito atual) |
| Saneamento | acertar grupo | `GRUPO_CORRIGIDO` | sim: 98,5% (gabarito atual) |
| Saneamento | dado ausente vem do catálogo do fabricante ou de confirmação manual | `09_enriquecer.py` (não rodado nesta sessão); completações sugeridas (`14`) | **não** |
| Cadastro | pedido em texto livre, ficha ou catálogo vira cadastro no padrão | `04_extrair.py --pedidos` (só extração) | **não** |
| Cadastro | conferir se o item já existe antes de criar | — | **não implementado** |
| Cadastro | devolver o pedido quando falta informação | lista `PENDENTES` + perguntas do `14` | **não implementado** como fluxo |
| Enriquecimento | buscar em catálogo e norma, conferir antes de gravar, registrar a fonte | `09_enriquecer.py` | **não** |
| Enriquecimento | os 15 últimos registros são produtos reais | estrato `plantados` do gabarito | parcial |
| Exemplo | parafuso sem classe de resistência | caso equivalente: `PARAFUSO SEXTAVADO M12X50 8.8 DIN 933` sem acabamento | pendência listada |
| Exemplo | porca com NCM de parafuso | caso equivalente: NCM da coluna contraria a classe (gabarito: arruela 7318.22 → 7318.21) | sim |
| Exemplo | a mesma válvula com três códigos | caso equivalente: `29618759` × `16000573` (gaveta 6POL = DN150, CF8M) | sim, amostra |
| Entregável | MVP funcional demonstrado | pipeline + catálogo; não há interface | **não** |
| Entregável | análise de mercado e do problema | `scripts/analise_mercado.py`, páginas de placar | parcial |
| Entregável | pitch de 5 minutos | — | **não** |

E uma linha por pergunta do briefing ("O que custa mais caro: juntar dois
itens diferentes ou deixar uma duplicidade passar?", "Quando a decisão pode
ser automática?", "Como provar que a base ficou melhor?"...), com a resposta
do projeto e o número que a sustenta.

### Entregáveis

- `docs/14-checklist-briefing.md`, com a tabela acima completa, uma linha por
  exigência e por pergunta, e o caso equivalente de cada exemplo (antes e depois);
- a lista do que falta, em ordem de impacto no pitch.

**Pronto quando:** toda exigência tem um status e, quando houver, o número e o
arquivo que a sustentam.

**Quem faz:** agente. **Esforço:** baixo (1 a 2 h).

---

## V4 · Valor financeiro como faixa

**Objetivo:** trocar "R$ 30,3 mi em capital redundante" por uma faixa que
desconta as junções erradas, com intervalo de confiança.

### Método

1. **Estratos de cluster**, porque a precisão não é igual em toda a base:
   - classe de referência (fabricante + part number) × especificação técnica;
   - cluster que depende de valor decidido pelo LLM × não depende;
   - tamanho: 2 códigos × 3 ou mais.
2. **Precisão por estrato**, vinda do `gold_juncao.csv` (pares rotulados
   `MESMO_ITEM` / `ITENS_DIFERENTES`), com IC de Wilson a 95%. Estrato com
   menos de 15 pares rotulados herda a precisão do estrato-pai e fica marcado.
3. **Capital ajustado:**
   `capital = Σ estratos (capital redundante do estrato × precisão)`.
   O limite inferior usa o limite inferior do IC de cada estrato; o superior,
   o superior.
4. Fazer o mesmo para **dispersão de preço** e **valor negociável em conjunto**,
   que o `06_juntar.py` também reporta.
5. **Sensibilidade:** o capital sem os clusters que dependem do LLM, e sem os
   que têm algum código em revisão.

### Entregáveis

- `avaliacao/30_valor_financeiro.py` → `avaliacao/valor_financeiro.md`
- a frase do pitch, gerada pelo script: *"entre R$ X e R$ Y milhões em capital
  parado em código duplicado (IC 95%), dos quais R$ Z não dependem de nenhum
  modelo"*.

**Plano B,** se o gabarito da junção atrasar: conferir à mão 100 clusters
sorteados por estrato (cerca de 1 h) e usar essa precisão, marcada como
amostra interna.

**Pronto quando:** o `.md` traz a faixa, a precisão por estrato e a análise
de sensibilidade, todas recalculáveis pelo script.

**Quem faz:** agente (script) + o gabarito da junção. **Esforço:** baixo
depois que a precisão existir.

---

## Como aplicar

Cada frente pode ir para um agente separado. Para isso, mande o trecho da
frente junto com o bloco "Regras que valem para as quatro frentes". Para não
haver colisão entre agentes no mesmo repositório:

| Frente | Arquivos que pode alterar |
|---|---|
| V1 | `scripts/rodar_completo.sh`, a opção `--congelar-aprendizado` em `scripts/04_extrair.py` e no `Aprendizado`, `artefatos/manifesto.json` |
| V2 | só `avaliacao/` (arquivos `*cadastro*`, `gold_unidade`, `gold_descricao`, `gold_sobrevivente`) |
| V3 | só `docs/14-checklist-briefing.md` |
| V4 | só `avaliacao/30_valor_financeiro.py` e `avaliacao/valor_financeiro.md` |

Ao terminar cada frente: rodar os testes, gerar o `.md` de resultado e commitar
só os arquivos da própria frente.
