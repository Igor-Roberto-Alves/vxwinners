# Custo de LLM: o que gastamos e o que gastaríamos com LLM em tudo

> **Como ler.** 🟢 é **medido** — chamada que de fato aconteceu, com tokens ou custo
> registrados em artefato ou log. 🟡 é **estimado** — o contrafactual, calculado sobre os
> prompts reais com uma razão caractere/token medida (seção 2). Nada aqui foi digitado à mão:
> `scripts/27_custo_llm.py` reproduz a tabela inteira e grava `artefatos/custo_llm.json`.
>
> ```bash
> .venv/bin/python scripts/27_custo_llm.py
> ```
>
> O script **não chama o Bedrock**: não gasta nada para dizer quanto se gastaria.

---

## 1. A resposta em quatro números

| | |
|---|---:|
| **Gasto real de LLM em produção**, nos 23.554 registros da base e nos 520 pedidos | **US$ 40,35** 🟢 |
| Mais o benchmark que escolheu as soluções (10 × 4 campos, pesquisa, não se repete) | US$ 173,62 🟢 |
| **Se o LLM fosse a única camada**, uma execução da mesma base, mesmo modelo | **US$ 228,59** 🟡 |
| A mesma coisa no modelo mais caro de tabela (Fable 5) | US$ 2.285,87 🟡 |

**A aposta da arquitetura, em uma frase:** as camadas baratas custam **US$ 0** por chamada e
resolvem a maioria das caixas; o LLM é perguntado 23.595 vezes em vez de 141.287, e isso é a
diferença entre US$ 40 e US$ 229 — **5,7×** — por execução.

**E o resíduo é o que importa.** Na tarefa em que as duas abordagens fazem a mesma coisa (ler
atributos e decidir classe, isto é, tudo menos o preenchimento de FABRICANTE), a comparação é
direta: **US$ 19,90 medidos contra US$ 168,08 estimados, 8,4×**.

---

## 2. Por que o contrafactual é defensável

Regra de três sobre custo de LLM é chute. Este número não é, por três razões.

**a) O prompt é o de verdade.** Para cada um dos 23.554 registros o script monta o prompt que
`src/saneamento/llm.py` manda ao Bedrock — o mesmo `SISTEMA`, o mesmo `_prompt()`, o mesmo
schema de tool use com o `enum` da classe. Não é um prompt hipotético: é o que custaria.

**b) A razão caractere/token é medida, não assumida.** A rodada
`artefatos/medicao_pedidos/3_bert_llm/` é a única do projeto com tokens reais em log: 37
chamadas, 0 do cache, **125.402 tokens de entrada e 9.284 de saída**. Reconstruir esses 37
prompts (os 37 pedidos com `escalado: true`) dá a razão deste formato de prompt:

| | Caracteres | Tokens reais | Razão |
|---|---:|---:|---:|
| entrada | 264.193 | 125.402 | **2,107 car/token** |
| saída | 10.585 | 9.284 | **1,140 car/token** |

**Isto corrige o `--so-contar`.** Os scripts 12 e 24 convertem caractere em token por uma
convenção de **3,5 caracteres** — que conta **40% menos token** do que o real, porque o prompt é
denso em número, pontuação e valor de `enum`. Toda estimativa deles sai baixa na mesma proporção.

A nota de [`11-rodar-llm.md`](11-rodar-llm.md) — *"a estimativa de custo do script 11 está 4
vezes abaixo do real"* — tem **outra** causa, e vale registrar para não arrumar o lugar errado:
o `11_canonizar_termos.py` não usa a convenção de 3,5, usa um chute fixo de **220 tokens de
entrada por termo** (`220 / 1e6 * 1.00`), que ignora o `SISTEMA` do próprio script (~520 tokens)
e o `enum` do atributo no tool use. O custo medido implica cerca de **1.300 tokens por termo**
(US$ 1,32 ÷ 939, descontada a saída), seis vezes o chute. Nos dois casos o modelo não custou
mais que o esperado: a conta é que estava errada.

**c) O resultado afere contra uma medição real.** O item (a) do contrafactual é exatamente a
chamada do `10_desempatar_llm.py`, só que em todos os registros em vez de 1.370. Os dois custos
por registro têm de bater, e batem:

| | US$ por registro |
|---|---:|
| contrafactual, atributos (estimado) | 0,00477 🟡 |
| desempate real, 1.370 registros (medido) | 0,00404 🟢 |

A diferença de 18% é esperada e tem sinal certo: no contrafactual o modelo preenche **todas** as
caixas, e escreve mais na saída do que no desempate, onde preenche só as que ficaram em dúvida.

---

## 3. Gasto real, etapa por etapa 🟢

| Etapa | Perguntas | Custo | Fonte |
|---|---:|---:|---|
| `11` canonizar termos que o PDM recusou | 939 | US$ 1,32 | [`11-rodar-llm.md`](11-rodar-llm.md) |
| `10` desempate de CONFLITO e AMBÍGUO | 1.370 | US$ 5,53 | [`11-rodar-llm.md`](11-rodar-llm.md) |
| `12` detecção de dado genérico (caixas com sinal) | 1.919 | US$ 2,92 | [`12-dado-generico.md`](12-dado-generico.md) §1 |
| `12` detecção de dado genérico (todas as caixas) | 6.382 | US$ 9,83 | [`12-dado-generico.md`](12-dado-generico.md) §6 |
| `08` preencher FABRICANTE nos faltantes (Sonnet 5, em lote) | 12.909 | US$ 20,45 | `preenchimento/saida/resumo_preenchimento.json` |
| `24` aprender tradução de classe (catálogo em inglês) | 38 | US$ 0,13 | `artefatos/medicao_pedidos/sujeito_aprendido_*.json` |
| `04` os 520 pedidos com todas as camadas ligadas | 38 | US$ 0,17 | `artefatos/medicao_pedidos/3_bert_llm/execucao.log` |
| **Total em produção** | **23.595** | **US$ 40,35** | |
| *+ benchmark das 10 soluções × 4 campos* | | *US$ 173,62* | `preenchimento/benchmark.csv` |
| **Total do projeto** | | **US$ 213,97** | |

Quatro observações sobre o que entra nessa conta:

- **"Perguntas", não requisições.** O `08_preencher.py` manda os itens de FABRICANTE em lote
  (`"Itens:\n" + lista`), então ali 12.909 é o número de campos perguntados. Pergunta é a
  unidade comparável com o contrafactual, que também poderia ser batelado.
- **FABRICANTE rodou em Sonnet 5, não em Haiku.** É o único campo em que o LLM ganha o
  benchmark (seção 5), e ali o projeto pagou pelo modelo melhor. Metade do gasto real do
  projeto é esse único campo.
- **O benchmark é pesquisa, não operação.** Os US$ 173,62 foram pagos uma vez para descobrir
  qual solução ganha em cada campo. Num cliente novo não se repete: já se sabe a resposta.
- **A soma de US$ 19,60 que aparece na [`12-dado-generico.md`](12-dado-generico.md) §6 continua
  certa** — ela cobre só o pipeline de atributos (termos, desempate e detecção). Os US$ 40,35
  incluem também o preenchimento de FABRICANTE e os pedidos.

### 3.1 Por que esse número não cresce a cada execução

Três mecanismos, em ordem de efeito:

1. **A pergunta é por termo, não por registro.** `ZINC` é perguntado uma vez e vale em toda
   linha que o traga. A [`09-pipeline-correto.md`](09-pipeline-correto.md) mediu essa
   granularidade: **1.963 dúvidas distintas em 11.852 registros**, US$ 1,52 por termo contra
   US$ 44,60 se fosse por registro.
2. **A resposta vira regra.** O que o LLM canoniza entra no `aprendizado.json` e decide sozinho
   na execução seguinte, sem chamada — é também o que a tela *Interferência de IA* audita: 487
   regras, 251 delas decidindo 4.819 linhas.
3. **O cache por hash** (`artefatos/cache_llm/`, 1.393 respostas; `cache_deteccao/`, 7.933)
   devolve a pergunta repetida de graça.

O resultado: as duas rodadas do teste de determinismo
(`scripts/17_testar_determinismo.sh`, que roda a extração com `--sem-llm
--aplicar-desempates`, aplicando respostas já gravadas) custaram **US$ 0**. Sem camada barata,
cada uma pagaria o preço inteiro: **US$ 457,17 pelas duas** 🟡.

---

## 4. O contrafactual: o LLM como única camada 🟡

Sem regras, gazetteer, gramática, dicionário e BERT, o modelo decide tudo: uma pergunta por
registro para a classe, outra para os atributos, e os quatro campos de identidade preenchidos em
todas as linhas — porque sem camada barata não se sabe quais linhas estão faltando.

| O que o LLM faria | Perguntas | Tokens de entrada | Tokens de saída | Custo |
|---|---:|---:|---:|---:|
| **a** · atributos, 1 pergunta por registro | 23.517 | 79,27 M | 6,56 M | US$ 112,10 |
| **b** · classe contra a lista fechada de sujeitos | 23.554 | 47,72 M | 1,65 M | US$ 55,98 |
| **c** · FABRICANTE em toda linha | 23.554 | 8,72 M | 1,49 M | US$ 16,17 |
| **c** · REFERENCIA_FABRICANTE em toda linha | 23.554 | 8,12 M | 0,40 M | US$ 10,13 |
| **c** · NCM em toda linha | 23.554 | 10,48 M | 1,52 M | US$ 18,10 |
| **c** · GRUPO_MERCADORIA em toda linha | 23.554 | 8,56 M | 1,51 M | US$ 16,11 |
| **Total, uma execução, Haiku 4.5** | **141.287** | **162,87 M** | **13,14 M** | **US$ 228,59** |

Os itens (a) e (b) são montados prompt a prompt, pelo método da seção 2. O item (c) não passa
pela conversão caractere/token: o benchmark já mediu os quatro campos com o **mesmo modelo** do
pipeline (`llm_fewshot_haiku`) e registrou os tokens reais de 2.000 predições em
`preenchimento/benchmark.csv` — basta trazer o token por predição para a base inteira.

### 4.1 O que multiplica

**Modelo.** Os mesmos 162,87 M de tokens, no preço de tabela de cada um
(`preenchimento/bedrock_util.py`):

| Modelo | Custo | |
|---|---:|---|
| Haiku 4.5 | US$ 228,59 | o que o pipeline usa |
| Sonnet 5 | US$ 457,17 | 2× |
| Opus 5 | US$ 1.142,94 | 5× |
| Fable 5 | US$ 2.285,87 | 10× |

**Reexecução.** US$ 228,59 **por execução**, contra US$ 0 a partir da segunda hoje.

### 4.2 O desconto que o contrafactual mereceria, e por que não muda a conclusão

Seria desonesto deixar de fora. O prefixo do prompt — `SISTEMA`, a lista de atributos da classe
e o schema do tool use — repete em todo registro da mesma classe: **78,2 M dos 79,3 M** tokens
de entrada do item (a), e **46,7 M dos 47,7 M** do item (b). Com *prompt caching* e a execução
agrupada por classe, ele é escrito uma vez e lido nas demais, a 10% do preço
(`backend/app/llm/cliente.py`):

| | Sem cache | Com cache |
|---|---:|---:|
| a · atributos | US$ 112,10 | US$ 41,85 |
| b · classe | US$ 55,98 | US$ 13,99 |
| **Total** | **US$ 228,59** | **US$ 116,35** |

Duas ressalvas, nas duas direções:

- O pipeline **não usa** prompt caching hoje: o cliente é `boto3 converse` sem `cachePoint`
  (pendência registrada em [`00-estado-do-projeto.md`](00-estado-do-projeto.md)).
- **O desconto vale para os dois lados.** As chamadas do resíduo têm o mesmo prefixo e cairiam
  na mesma proporção — a estimativa antiga de "US$ 11 → US$ 5,50 com caching agrupado por
  classe" é justamente isso. A razão entre os dois lados se mantém, e por isso a comparação
  honesta é **sem cache nos dois**: US$ 40,35 contra US$ 228,59.

---

## 5. O argumento que não é de custo: em 3 dos 4 campos, o barato **acerta mais**

Se o LLM em tudo fosse só mais caro, seria uma escolha de orçamento. O benchmark diz outra
coisa. Nas duas colunas de custo, a solução roda na base inteira (23.554 linhas), para ficarem
comparáveis — o gasto real da seção 3 é menor porque só rodou nas linhas faltantes.

| Campo | Solução aplicada | top-1 | Na base inteira | LLM no modelo do pipeline | top-1 | Na base inteira |
|---|---|---:|---:|---|---:|---:|
| REFERENCIA_FABRICANTE | `regras` | **0,844** | US$ 0,00 | `llm_fewshot_haiku` | 0,811 | US$ 10,13 |
| NCM | `tfidf_lr` | **0,910** | US$ 0,00 | `llm_fewshot_haiku` | 0,887 | US$ 18,10 |
| GRUPO_MERCADORIA | `knn_cohere` | **0,966** | US$ 1,09 | `llm_fewshot_haiku` | 0,965 | US$ 16,11 |
| FABRICANTE | `llm_fewshot_sonnet` | **0,843** | US$ 46,40 | `llm_fewshot_haiku` | 0,833 | US$ 16,17 |

Em três dos quatro campos, pagar pelo LLM compraria **menos acerto**. Só em FABRICANTE o LLM
ganha — e ali o projeto não só o usou, usou o **modelo mais caro** que ganhou o campo (Sonnet 5,
os US$ 20,45 da seção 3, metade do gasto do projeto). A arquitetura não economiza por avareza:
ela paga o LLM onde ele é o melhor e não paga onde ele perde.

E o andaime é o que faz a diferença, não o modelo: o `llm_naive` — o mesmo Haiku perguntado sem
lista fechada, sem tool use e sem validador — tira **top-1 de 0,000** em GRUPO_MERCADORIA e
**0,025** em NCM, pelo mesmo preço. O custo não é a única coisa que as camadas baratas protegem.

---

## 6. Para o pitch

- "**Quanto custa a IA?**" US$ 40,35 nesta base de 23.554 registros. Menos de **US$ 0,002 por
  registro**. Em preço de saneamento (R$ 15 por registro, [`15-modelo-de-negocio.md`](15-modelo-de-negocio.md)),
  o LLM é ~0,06% da receita.
- "**E se vocês usassem IA para tudo?**" US$ 228,59 por execução — 5,7× — e acertaríamos menos em
  3 dos 4 campos de identidade. Com o modelo mais caro, US$ 2.285,87.
- "**E quando a base dobrar?**" O custo acompanha o resíduo, não a base, e a dúvida se repete:
  1.963 distintas em 11.852 registros (seção 3.1). Quanto maior a base, maior a chance de a
  pergunta já estar respondida no dicionário. A curva não foi medida; a direção é essa. E a
  segunda execução da mesma base custa US$ 0, isso sim medido.
- **O que não dizer:** que o contrafactual é medido. Ele é estimado sobre prompts reais, com uma
  razão caractere/token medida e aferida contra uma rodada real (seção 2). O gasto real é que é
  medido.

---

## 7. O que falta

1. **Rodar uma amostra do contrafactual de verdade.** 500 registros com o LLM fazendo tudo
   (~US$ 5) trocariam a estimativa do item (a) por medição, e dariam de brinde a acurácia do
   "LLM em tudo" contra o gabarito — o que hoje é o elo mais fraco do argumento da seção 5, que
   compara campos de identidade e não atributos.
2. **Corrigir as estimativas do `--so-contar`.** Nos scripts 12 e 24, trocar a convenção de 3,5
   caracteres por token pelo valor medido, 2,107 (seção 2) — hoje subestimam em 40%. No script
   11, trocar o chute fixo de 220 tokens por termo por uma conta sobre o prompt real, que
   inclui o `SISTEMA` e o `enum` do atributo.
3. **Ligar prompt caching** no cliente, que corta o custo real do resíduo quase na metade sem
   mudar nenhuma resposta.
