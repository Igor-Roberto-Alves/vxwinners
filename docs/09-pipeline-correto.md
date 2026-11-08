# O pipeline correto: quem decide o quê, e em que ordem

Documento de desenho. Define a responsabilidade de cada camada, de cada modelo e
de cada arquivo, e a ordem em que atuam.

Existe porque a ordem hoje está **espalhada em três lugares** —
`ExtratorLexico._um_atributo`, `ExtratorLexico.extrair` e `Arbitro._decidir` — e
isso produziu quatro bugs da mesma família em duas horas de depuração. A seção 9
marca o que já está assim e o que divergiu.

---

## 1. O princípio: ordenar por força da evidência

Uma camada vem antes de outra quando sua evidência é **mais direta**. Não é sobre
custo computacional nem sobre sofisticação — é sobre quão perto a camada está do
que o cadastro realmente afirmou.

```
FORTE   o cadastro escreveu o nome da caixa ao lado do valor
        "DIAMETRO INTERNO:39MM"           -> nao ha inferencia nenhuma

        o valor permitido aparece literal no texto
        "...DIN 933..." e DIN 933 esta na lista   -> casamento, nao inferencia

        sinonimo curado de dominio
        'ACO CARB' -> ACO CARBONO          -> mapa escrito por pessoa, versionado

        dicionario aprendido
        'BICROMATIZADO' -> ZINCADO AMARELO -> mapa gerado por LLM, a curar

        gramatica de grandeza
        '35MM' -> 35MM                     -> forma certa; POSICAO e inferida

        restricao de dominio
        alojamento > eixo > largura        -> conhecimento de engenharia

        derivacao por regra do PDM
        'M12X50' -> BITOLA M12 + COMP 50MM -> regra 2; e DEDUCAO, nao leitura

        coluna do ERP
        FABRICANTE = 'METSO'              -> outro campo do registro

        BERT                              -> recorte aprendido por posicao e forma

        embedding                         -> aproximacao semantica

FRACO   LLM                               -> julgamento sobre alternativas
```

Duas consequências que eu tinha errado:

- **A regra 2 do PDM (`M12X50`) é dedução, não leitura.** Ela perde para o
  rótulo. No registro `27422515` o cadastro escreve `ROSCA:MF` e
  `BITOLA:M12X1,5`, e a regra 2 sobrescrevia com `METRICA GROSSA` e `M12` —
  deduzindo contra o que estava escrito.
- **O LLM é o mais fraco, não o mais forte.** Ele julga; as camadas acima leem.

---

## 2. A distinção que faltava: precedência ≠ execução

Este é o erro de fundo.

```
ORDEM DE PRECEDENCIA   quem GANHA quando duas camadas acham valores diferentes
ORDEM DE EXECUCAO      quem RODA, e se roda sempre ou so quando falta valor
```

Eu tratei as duas como a mesma coisa e implementei **saída antecipada**: a
primeira camada que achava valor retornava, e as seguintes nunca rodavam.

Isso destrói a informação mais valiosa do pipeline. Hoje, **52,9% dos valores
aceitos vêm de `acordo`** — regra e BERT chegando ao mesmo valor por caminhos
independentes. Esse acordo só existe porque o BERT roda **mesmo quando a regra já
achou**. Toda camada que sai antecipadamente deixa de produzir esse sinal.

E foi a causa dos quatro bugs: saída antecipada esconde divergência em vez de
registrá-la.

**Regra:** toda camada que pode contribuir **roda**. A precedência resolve depois.

---

## 3. As cinco fases

```
┌─ FASE 1 · COLETA ─────────────────────────────────────────────────────────┐
│  Toda camada aplicavel propoe um candidato para cada caixa.               │
│  Independentes entre si. Nenhuma saida antecipada.                        │
│  Resultado: 0..N candidatos por caixa, cada um com fonte e evidencia.     │
└───────────────────────────────────────────────────────────────────────────┘
                                   │
┌─ FASE 2 · VALIDACAO ──────────────────────────────────────────────────────┐
│  Cada candidato passa pelo validador do PDM, independente da fonte.       │
│  Candidato recusado NAO e descartado em silencio: vira candidato a        │
│  entrada de dicionario (e ali que estao os 1.228 termos que o LLM         │
│  canonizou por US$ 1,52).                                                 │
└───────────────────────────────────────────────────────────────────────────┘
                                   │
┌─ FASE 3 · ARBITRAGEM ─────────────────────────────────────────────────────┐
│  Resolve por PRECEDENCIA e mede ACORDO.                                   │
│    candidatos concordam         -> aceita, confianca alta (e o sinal bom) │
│    discordam                    -> vence a precedencia mais forte,        │
│                                    e a caixa vai para escalada            │
│    nenhum candidato valido      -> PENDENTE (nao e escalada: nao ha o     │
│                                    que ler)                               │
└───────────────────────────────────────────────────────────────────────────┘
                                   │
┌─ FASE 4 · ESCALADA ───────────────────────────────────────────────────────┐
│  LLM, so nas caixas que a fase 3 nao resolveu. Nunca por registro inteiro.│
│  Resolve por TERMO quando possivel (1.963 duvidas distintas em 11.852     │
│  registros), e o resultado alimenta o dicionario aprendido.               │
└───────────────────────────────────────────────────────────────────────────┘
                                   │
┌─ FASE 5 · PORTAO E SAIDA ─────────────────────────────────────────────────┐
│  Monta a descricao na ordem do PDM, resolve unidade e NCM, calcula a      │
│  chave de identidade. Nada entra sem obedecer as invariantes.             │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 4. As camadas, uma por uma

| # | Camada | O que propõe | Com que evidência | Roda sempre? |
|---|---|---|---|---|
| 0 | **rótulo** | valor do par `ATRIBUTO: VALOR` | o cadastro nomeou a caixa | sim |
| 1 | **gazetteer** | valor permitido que aparece literal | casamento de texto | sim |
| 2 | **sinônimo curado** | valor via mapa de domínio | `sinonimos.py`, versionado | só se 0 e 1 falharem |
| 3 | **aprendido** | valor via mapa gerado por LLM | `aprendizado.json` | só se 0–2 falharem |
| 4 | **gramática** | grandeza formatada | regex + conversão de unidade | sim, em caixa NUMERICA |
| 5 | **domínio** | atribuição posicional | alojamento > eixo > largura | quando a contagem casa |
| 6 | **regra 2 do PDM** | desmembra `M12X50` | dedução autorizada pelo PDM | sim |
| 7 | **coluna do ERP** | valor de campo homônimo | outro campo do registro | sim |
| 8 | **BERT** | qual trecho é de qual caixa | modelo treinado | **sim, sempre** |
| 9 | **embedding** | trecho ≈ valor permitido | similaridade com margem | só gera candidato |
| 10 | **LLM** | escolhe entre alternativas | julgamento | só na escalada |

A coluna "roda sempre" é o conserto: hoje várias saem antecipadamente.

---

## 5. Responsabilidade de cada modelo

### BERT — `distilbert-base-multilingual-cased`, token classification BIO

**Responsável por:** decidir **qual trecho do texto pertence a qual caixa**.

```
RET. 110MM 15MM BASL NBR
  110MM -> B-DIAMETRO EIXO
  15MM  -> B-LARGURA
```

**Não é responsável por:** decidir o que o valor significa, converter unidade,
canonizar sinônimo, decidir a classe do item, decidir duplicidade.

| | |
|---|---|
| Entrada | tokens do texto, com os nomes de atributo removidos (igual ao treino) |
| Saída | uma etiqueta por palavra, agrupada em `atributo → trecho` |
| Treino | 61.869 anotações por distant supervision, 0 anotadas à mão |
| Métrica | F1 token 0,985 · precisão 1,000 · sequência exata 0,886 |
| É a única camada que preenche | caixa `LIVRE` (part number, modelo) |
| Validado por | split por `CODIGO_MATERIAL`, nunca por linha |

**Por que ele existe:** as caixas `LIVRE` não têm lista nem formato — nenhuma
regra alcança. Medido: as classes de referência do fabricante saíram de 55,7%
para 94,9% de chave fechada quando o BERT entrou.

**Dois cortes de probabilidade, e o que cada um alcança.** O decodificador usa
`argmax` por palavra: a palavra recebe o rótulo mais provável, seja ele 0,99 ou
0,31. Quem filtra depois é o `LIMIAR_BERT = 0,60` (`arbitro.py`), que olha a
**média** do span — e média esconde a palavra fraca: o recorte real
`INOX 316 EXTREMIDADES` (0,88 / 0,99 / 0,31) dá 0,73 e passa. O que o barrou foi
o enum do PDM, não a confiança; em caixa `LIVRE` não há enum para barrar.

Por isso existe também um piso **por palavra**
(`ExtratorBert(piso_palavra=…)`, `--piso-bert` no `04_extrair.py`): abaixo dele
a palavra vira `O` e **fecha** o span em vez de entrar nele. No mesmo texto:

```
piso 0,0  MATERIAL = 'INOX 316 EXTREMIDADES' (0,87) + 3 spans de lixo (0,19–0,49)
piso 0,8  MATERIAL = 'INOX 316' (0,99), o lixo não aparece
```

**Medido, e o veredito é "não ligue por enquanto":** `avaliacao/19_efeito_piso_bert.py`
reexecuta o pipeline nos 232 códigos do conjunto-ouro, um passe por piso. De 0,0
a 0,7 o resultado é o mesmo (±1 rótulo). Em 0,8: precisão 98,7% → 98,8%,
cobertura 90,4% → 90,2%, um erro a menos; nos campos sem enum, 91,7% → 94,3%,
que é **um** caso em 36 afirmados — dentro do ruído, com o mesmo IC (98%–99%)
nos dois lados.

Mexe pouco porque as duas travas que já existiam cobrem quase tudo: quando o
BERT acerta o rótulo, acerta com confiança alta (média 0,88 nos aceitos); quando
não, o `LIMIAR_BERT` sobre a média já barrava; e o span sujo era barrado pelo
enum. O piso só alcança o que escapava das duas.

**Alcance, fora do gabarito** (2.000 registros aleatórios, semente 42): piso 0,5
muda 12 decisões em 12 registros; piso 0,8 muda 42 em 41. E a mudança **não** é
só "afirmar menos" — ao derrubar o recorte do BERT, outra camada (regra léxica,
ordem do PDM, dicionário) assume e pode gravar um valor diferente. Nos dois
sentidos:

```
limpa    REFERENCIA FABRICANTE  'B2987-00 LUBR' -> 'B2987-00'   (caixa LIVRE, sem enum)
piora    FAIXA                  '0-25BAR'       -> '24,5BAR'
piora    DIAMETRO EIXO          '165MM'         -> '10MM'
```

O piso muda **quem decide**, não só quanto se afirma — e é por isso que ele fica
desligado por padrão (`0.0`), com a flag disponível para quem queira medir de
novo com um gabarito maior. Números completos em
`avaliacao/efeito_piso_bert.md`.

### Embedding — `intfloat/multilingual-e5-small`

**Responsável por:** medir similaridade entre um trecho e os valores permitidos,
e gerar candidato quando nada mais achou.

**Não é responsável por decidir.** Isso não é opinião, é medição: em 500
registros, **nenhuma** proposta dele atingiu a banda que dispensa o LLM. Todas as
71 caíram na banda do meio, e a maioria era ruído (`VER DESENHO` → `VEICULO
LEVE`).

A razão é estrutural — o PDM nomeia as coisas com diferença mínima:

```
cos(ACO INOX 304, ACO INOX 316) = 0,963
cos(ROSCA NPT,    ROSCA BSP)    = 0,965
cos(DIN 931,      DIN 933)      = 0,959
937 de 946 pares de classes acima de 0,85
```

A informação discriminante está em **uma palavra**, e o embedding faz média sobre
a frase. **Uso legítimo:** blocking na junção (gerar pares candidatos entre 23
mil registros antes da comparação exata).

### LLM — `us.anthropic.claude-haiku-4-5` (volume) / `claude-sonnet-5` (difícil)

**Responsável por:** (a) escolher entre alternativas plausíveis quando duas
camadas discordam; (b) canonizar um termo que o enum do PDM recusa.

**Não é responsável por:** preencher caixa sem evidência no texto, escolher
variante quando o texto não diz qual.

| | |
|---|---|
| Quando é chamado | caixa em `CONFLITO`, `AMBIGUO` ou `INVALIDO` |
| Quando **não** é chamado | ninguém viu nada no texto → `PENDENTE` |
| Granularidade | por **termo**, não por registro (1.963 dúvidas vs 11.852 registros) |
| Custo medido | US$ 1,52 por termo · US$ 44,60 por registro |
| Saída forçada | tool use com `enum` da classe: não consegue emitir valor fora da lista |
| Taxa de desperdício | 0,8% recusado pelo validador |
| Auditoria manual | 19 de 20 caixas corretas |

**O que o validador NÃO protege, e por isso precisa de trava em código:** valor
que está no enum e mesmo assim é errado.

```
'ZINCADO' -> ZINCADO BRANCO    (lista tem BRANCO e AMARELO)
'ACO'     -> ACO CARBONO       (lista tem CARBONO, 304, 316)
'INOX'    -> ACO INOX 304      (lista tem 304 e 316)
```

Os três são valores válidos — o validador os aceita intactos. O prompt sozinho
errava **3 de 12** casos adversários. Com as travas (`subcadeia`, `palavra`,
`gêmeo numérico`), 12 de 12. Mais a regra de prompt contra escolher variante não
declarada, que elevou os casos adversários para 5 de 5 — ao custo de 43 termos
que passaram a ser declinados.

**Lição registrada:** `confirmações >= 2 → confiável` **não** protege contra erro
de modelo, porque erro de modelo é sistemático: ele se repete e por isso se
auto-confirma. 7 das 10 entradas removidas do dicionário estavam marcadas
confiáveis, uma com 25 confirmações. O sinal válido é concordância entre fontes
**independentes**, não repetição da mesma fonte.

---

## 6. Responsabilidade de cada arquivo

| Arquivo | Responsável por | **Não** é responsável por |
|---|---|---|
| `texto.py` | normalizar texto; converter unidade (psi→bar, DN→POL, AWG→mm²); formatar grandeza; desmembrar `M12X50` | conhecer classe ou atributo |
| `pdm.py` | ler o PDM da planilha; decidir se atributo condicional se aplica | extrair ou validar |
| `caixas.py` | definir a caixa, seu tipo (`TEXTUAL`/`NUMERICA`/`LIVRE`) e as bandas de confiança | preencher caixa |
| `rotulos.py` | `pares()`: achar `ATRIBUTO: VALOR` (camada 0) e gerar o treino do BERT | decidir valor final |
| `regras.py` | achar a classe (sujeito); camadas 0–7 | julgar divergência |
| `sinonimos.py` | mapa de domínio **curado por pessoa**, versionado no git | aprender sozinho |
| `aprendizado.py` | mapa **gerado por LLM**, persistente, com procedência e curadoria | ser confiado sem revisão |
| `bert.py` | treinar e executar o recorte | canonizar valor |
| `embeddings.py` | medir similaridade com margem e trava de gêmeo numérico | decidir valor |
| `arbitro.py` | **única** autoridade sobre precedência e acordo; definir o estado da caixa; decidir escalada | extrair |
| `llm.py` | chamar o Bedrock com saída estruturada; travas de ambiguidade; cache versionado pelo prompt | preencher o que não está no texto |
| `validador.py` | **o portão**: invariantes do PDM; montar descrição, unidade, NCM e chave de identidade | propor valor |
| `enriquecimento.py` | completar caixa vazia com fonte externa **e procedência** | sobrescrever valor extraído |
| `pipeline.py` | orquestrar as 5 fases | conter regra de decisão |

**A regra mais importante desta tabela:** `arbitro.py` é a **única** autoridade
sobre precedência. Hoje ela está também em `_um_atributo` (saída antecipada) e em
`extrair` (sobrescrita pela regra 2) — e é exatamente de onde vieram os bugs.

---

## 7. O que é cada estado de caixa

| Estado | Significa | Vai para o LLM? |
|---|---|---|
| `ACEITO` | candidato válido, sem divergência | não |
| `CONFLITO` | duas camadas, dois valores | **sim** |
| `AMBIGUO` | o dicionário casou 2+ valores permitidos | **sim** |
| `INVALIDO` | o BERT recortou algo que o enum recusa | **sim** — é o material do dicionário |
| `INCERTO` | só o BERT preencheu, abaixo do limiar | sim |
| `PENDENTE` | ninguém viu nada no texto | **não** — enriquecimento ou devolução |

E o estado do **registro**:

| Estado | Critério |
|---|---|
| `SANEADO` | classe + descrição no padrão + unidade + NCM resolvidos (definição do briefing) |
| `COMPLETO` | saneado **e** todas as caixas obrigatórias cheias |
| `REVISAO_HUMANA` | caixa com duas respostas plausíveis que o LLM não resolveu |
| `PENDENTE` | falta dado que não está no texto |
| `FORA_DO_PDM` | nenhuma classe do padrão serve |

---

## 8. Como validar cada parte

| O que validar | Como | Número atual |
|---|---|---|
| **Fidelidade de leitura** | gabarito automático pelos rótulos explícitos, nos registros fora do treino do BERT | **F1 94,0%** (7.755 caixas) |
| Caixas de vocabulário fechado | mesmo gabarito, por atributo | **100%** em NORMA, FABRICANTE, MATERIAL, TIPO, CLASSE RESISTENCIA |
| Recorte do BERT | split por código, F1 por token | 0,985 · precisão 1,000 |
| Correção de domínio | 15 produtos reais da base, contra catálogo | **32 acertos, 0 erros** |
| Decisões do LLM | auditoria manual | 19 de 20 |
| Não juntar o que não deve | regra 13 nos filtros intercambiáveis | 0 junções indevidas |
| Perda de informação | token da linha que nenhuma caixa explica | **22,8%** |
| Invariantes do PDM | 353 testes | passando |
| **Contribuição por camada** | assertar que cada fonte preenche > 0 caixas | **não existe — é o teste que falta** |

O último é o mais importante e não existe. Quatro vezes neste projeto uma camada
entrou no código e ficou **sem efeito**, com o pipeline rodando e entregando
menos, sem acusar nada: `sinonimos.py` não ligado no caminho principal; o
dicionário aprendido com a chave de evidência não casando; `pares()` usado só
para treino; e a camada 0 recebendo texto já normalizado, sem os dois-pontos.

```python
def test_toda_camada_contribui():
    """Camada que preenche ZERO caixas esta desligada, e o pipeline nao acusa."""
    fontes = Counter(d.fonte for r in amostra for d in r.decisoes.values() if d.valor)
    for camada in ("rotulo", "gazetteer", "sinonimo", "aprendido",
                   "gramatica", "dominio", "bert", "coluna_erp"):
        assert fontes[camada] > 0, f"camada {camada} nao contribuiu nada"
```

---

## 9. Divergência entre este desenho e o código de hoje

| Item | Desenho | Hoje | Efeito |
|---|---|---|---|
| ✅ Camada 0 roda | sim | **sim** | corrige os 3 maiores erros do gabarito |
| ✅ Regra 2 perde do rótulo | sim | **sim** | `ROSCA:MF` deixa de virar `METRICA GROSSA` |
| ✅ Atributo opcional disputa a grandeza | sim | **sim** | `SECAO` para de copiar o diâmetro interno |
| ✅ Teste de contribuição por camada | sim | **sim** | quebra se uma camada ficar sem efeito |
| ✅ Artefato parcial com nome próprio | sim | **sim** | `--limite` não sobrescreve a base inteira |
| ❌ Precedência num lugar só | `arbitro.py` | espalhada em 3 arquivos | foi a causa de 4 bugs |
| ❌ Sem saída antecipada | sim | sai antecipado | esconde divergência; perde o sinal de acordo |
| ❌ Escalada por caixa | sim | por registro (média ≥ 0,30) | 10.907 de 13.628 caixas `INVALIDO` nunca chegam ao LLM |
| ❌ Aprendido consultado sempre | sim | só quando nada casou | em `AMBIGUO` (28% das escaladas) nunca é perguntado |
| ❌ `SANEADO` ≠ `COMPLETO` | sim | um estado só | relatório subestima por ~50 pontos |

**Resolvido:** 5 de 10. As cinco pendentes são a fila de trabalho, em ordem de
impacto — e as duas primeiras (precedência num lugar só, sem saída antecipada)
são a refatoração que elimina a família de bug, não um bug individual.

### Prioridade entre irmãos de grandeza

Duas exigências que pareciam opostas foram reconciliadas por prioridade, e vale
registrar porque o raciocínio não é obvio:

- `DISCO ABRASIVO CORTE 115MM` tem **um** número e três caixas em MM. O diâmetro
  já estava certo e não pode ser perdido.
- Mas caixa **opcional** não pode copiar o primeiro número que achar — é como
  `SECAO` de `PDM031` recebia o valor de `DIAMETRO INTERNO`.

A regra: quando há **menos números que caixas**, distribui pelas de maior
prioridade (`obrigatório sempre` > `obrigatório condicional` > `opcional`) e
deixa as outras honestamente vazias. Quando a contagem **casa**, todas disputam
e a restrição de domínio decide.
