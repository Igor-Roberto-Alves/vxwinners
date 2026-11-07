# Como cada caixa é preenchida

Este documento explica a mecânica da extração: quem preenche cada caixa, em que
ordem, e por que. É o detalhe por dentro do passo 2 de `04-como-funciona.md`.

Contém também um erro de projeto **ainda não corrigido** (seção 6), marcado como
tal. Quando for corrigido, esta seção vira histórico.

---

## 1. A base tem dois tipos de linha

Essa distinção é a chave de tudo.

```
ROTULADA  — o nome do atributo esta escrito junto do valor
            59,9% dos registros (14.112 de 23.554)

  ARRUELA LISA, PARA PARAFUSO:M36, DIAMETRO INTERNO:39MM, DIAM EXTERNO:110 MM,
  E:8 MM, MATERIAL:CARBONO, ACAB:GEOMET, PADRAO:DIN 9021


TELEGRAFICA — so os valores, sem dizer de que atributo sao
            ~40% dos registros

  RET. 110MM 15MM BASL NBR
```

Na linha rotulada, **a resposta está escrita**. Na telegráfica, é preciso inferir
pela posição e pela forma. São dois problemas de dificuldade muito diferente, e o
pipeline precisa tratá-los como tal.

---

## 2. Os três tipos de caixa decidem quem pode preenchê-la

O tipo vem da coluna `FORMATO` / `VALORES_PERMITIDOS` da aba `ATRIBUTOS` do PDM.

| Tipo | Como se reconhece | Quem preenche |
|---|---|---|
| **TEXTUAL** | tem lista de valores permitidos | dicionário (busca a lista no texto) |
| **NUMERICA** | tem formato fixo (`numero + MM`, `fracao + POL`, `numero + BAR`) | gramática (regex + conversão de unidade) |
| **LIVRE** | nem lista nem formato (part number, modelo) | **só o BERT** |

Exemplo, classe `PDM004` (arruela lisa), as 7 caixas:

```
#  CAIXA               TIPO       OBR
1  PARA PARAFUSO       TEXTUAL     S    M6 | M8 | M10 | ... | M36
2  DIAMETRO INTERNO    NUMERICA    -    numero + MM
3  DIAMETRO EXTERNO    NUMERICA    -    numero + MM
4  ESPESSURA           NUMERICA    -    numero + MM
5  MATERIAL            TEXTUAL     S    ACO CARBONO | ACO INOX 304 | ACO INOX 316
6  ACABAMENTO          TEXTUAL     S    GALVANIZADO A FOGO | NATURAL | ... | ZINCADO BRANCO
7  NORMA               TEXTUAL     S    DIN 125 | DIN 9021
```

Repare: as três dimensões são **opcionais** nessa classe. Isso vai importar na
seção 5.

---

## 3. A cascata, camada por camada

Para cada caixa, da camada mais barata e certa para a mais cara e incerta. Se
resolveu, para; se não, desce.

```
1  LISTA DO PDM        o valor permitido aparece literal no texto
2  DICIONARIO CURADO   sinonimo de dominio ('ACO CARB' -> ACO CARBONO)
3  DICIONARIO APRENDIDO o que LLM/BERT ja resolveram antes
4  GRAMATICA           grandeza com formato fixo
5  BERT                recorta qual trecho pertence a qual caixa
6  LLM                 so o residuo em conflito
```

### Camada 1 e 2, caixa TEXTUAL — funciona bem

```
caixa MATERIAL, lista = [ACO CARBONO | ACO INOX 304 | ACO INOX 316]
texto:  "... MATERIAL:CARBONO, ACAB:GEOMET ..."

1. procura cada valor da lista dentro do texto  -> 'ACO CARBONO' nao aparece literal
2. dicionario de dominio: 'CARBONO' -> ACO CARBONO   -> ACHOU
```

Medido na base: **68% das caixas** são preenchidas assim, e outras 5% pelo
dicionário. É por isso que o LLM não é a primeira camada.

### Camada 4, caixa NUMERICA — e aqui está o problema

A gramática funciona por **contagem**:

```
caixa DIAMETRO INTERNO, formato = "numero + MM"

1. acha TODOS os numeros em MM no texto
2. conta quantas CAIXAS da classe disputam a familia MM
3. contagem bate?  distribui por restricao de dominio (externo > interno > espessura)
   nao bate?       pega o primeiro e marca AMBIGUO
```

A restrição de domínio é conhecimento de engenharia, e vale mais que modelo:
*o alojamento é sempre maior que o eixo, que é maior que a largura.* Resolve 782
registros de retentor sem nenhuma inferência.

Mas a contagem é frágil: **um número a mais no texto quebra a classe inteira.**

---

## 4. Quando o BERT entra

**Quando não há rótulo.** Ele é um classificador de token: põe uma etiqueta em
cada palavra dizendo de qual caixa ela é.

```
RET. 110MM 15MM BASL NBR

  RETENTOR   O                      <- 'O' = fora de caixa (e o sujeito)
  110MM      B-DIAMETRO EIXO        <- 'B' = comeco do valor
  15MM       B-LARGURA
  BASL       B-TIPO
  NBR        B-MATERIAL
```

### O detalhe elegante: as linhas rotuladas ensinam as telegráficas

O treino sai das próprias linhas rotuladas da base, **com os nomes dos atributos
removidos**:

```
linha rotulada da base            exemplo de treino gerado
ARRUELA LISA,                       ARRUELA   O
DIAMETRO INTERNO:39MM        ->     LISA      O
DIAM EXTERNO:110 MM                 39MM      B-DIAMETRO INTERNO
                                    110MM     B-DIAMETRO EXTERNO
```

Sem o rótulo no texto, o modelo é obrigado a aprender por **posição e forma** — e
é justamente isso que transfere para a linha telegráfica. Sem essa remoção ele
aprenderia apenas "copie o que vem depois dos dois pontos", e seria inútil no
alvo.

São **61.869 anotações, nenhuma feita à mão**. Resultado: F1 por token 0,985,
precisão 1,000, sequência 100% correta 0,886.

Só o BERT preenche caixa `LIVRE`. Medido: as classes de referência do fabricante
(filtros e sobressalentes) saíram de **55,7% para 94,9%** de chave de identidade
fechada quando o BERT entrou, porque o part number passou a ser recortado.

---

## 5. Quando a LLM é chamada

Só quando as camadas **discordam**, e só nas caixas em discordância:

| Situação | Vai para o LLM? |
|---|---|
| regra diz X, BERT diz Y, e X ≠ Y | **sim** |
| o dicionário casou dois valores permitidos no mesmo texto | **sim** |
| o BERT recortou um trecho que o enum do PDM recusa | **sim** — ele canoniza |
| ninguém achou nada | **não** |

A última linha é a regra mais importante do projeto: **se o dado não está no
texto, nenhum modelo pode preenchê-lo sem inventar.** Medido: 33% dos atributos
obrigatórios estão genuinamente ausentes. Esses casos vão para enriquecimento
(fonte externa, com procedência) ou devolução ao solicitante.

E o LLM não tem passe livre: a resposta dele passa pelo mesmo validador das
outras camadas. Valor fora da lista do PDM é recusado, venha de onde vier.

Medido: **18,4% dos registros** seriam escalados. Os outros 81,6% se resolvem sem
nenhuma chamada.

---

## 6. O erro: a gramática ignora o rótulo ⚠️ *não corrigido*

Rastreando o registro `16279976`:

```
LINHA:  ARRUELA LISA, PARA PARAFUSO:M36, DIAMETRO INTERNO:39MM,
        DIAM EXTERNO:110 MM, E:8 MM, MATERIAL:CARBONO, ACAB:GEOMET, PADRAO:DIN 9021

caixas da classe PDM004 na familia MM:  []          <- VAZIO
numeros em MM que o regex acha       :  39, 110, 8

resultado: DIAMETRO INTERNO = 39MM, estado AMBIGUO
```

Dois bugs somados:

**(a) A lista de concorrentes sai vazia.** Eu monto os concorrentes da família a
partir de `classe.obrigatorios`, e em `PDM004` as três dimensões são
**opcionais**. Então a gramática não vê concorrente, pega o primeiro número
(39, que por sorte está certo) e marca ambíguo porque sobraram três.

**(b) A restrição de domínio nunca roda para caixa opcional**, pela mesma razão.

Mas o erro de fundo é maior que os dois:

```
DIAMETRO INTERNO:39MM
^^^^^^^^^^^^^^^^ o nome da caixa esta colado no valor
```

**A resposta está escrita, rotulada, e a gramática não olha para o rótulo.** Ela
trata uma linha rotulada como se fosse telegráfica — conta números e adivinha a
ordem — quando bastava ler a palavra ao lado.

### O parser já existe e não está ligado

A função `pares()` em `src/saneamento/rotulos.py` acha pares `ROTULO: VALOR` e
resolve sinônimo de rótulo (`DIAM INT`→`DIAMETRO INTERNO`, `PADRAO`→`NORMA`,
`MAT`→`MATERIAL`). Nessa linha ela devolve, hoje, sem nenhuma mudança:

```
PARA PARAFUSO    = 'M36'       <- atributo do PDM004
DIAMETRO INTERNO = '39MM'      <- atributo do PDM004
DIAMETRO EXTERNO = '110 MM'    <- atributo do PDM004
MATERIAL         = 'CARBONO'   <- atributo do PDM004
NORMA            = 'DIN 9021'  <- atributo do PDM004
E                = '8 MM'      <- rotulo 'E' nao esta na tabela de sinonimos
```

Esse parser foi escrito para **gerar o treino do BERT** e nunca foi usado na
extração. Ou seja: os rótulos explícitos servem para ensinar um modelo a
adivinhar o que os rótulos já dizem, e na hora de extrair eles são ignorados.

É a mesma classe de erro que o `sinonimos.py`, que também existia e não estava
ligado no caminho principal — capacidade construída e deixada sem uso. Ligar o
dicionário rendeu **+5,1 pontos de SANEADO**.

### Quanto isso custa hoje

```
caixas em CONFLITO/AMBIGUO ..............  2.986

o texto JA TRAZ o rotulo do atributo ....  1.187   39,8%   <- resolveria de graca
texto sem rotulo (telegrafico) ..........  1.799   60,2%   <- ai sim e BERT/LLM
```

**40% dos conflitos são auto-infligidos.** E o custo real é maior que esse número,
porque há registros que nem chegam a conflito: a caixa simplesmente fica vazia
embora o valor esteja rotulado no texto.

### Por que não resolver isso com o LLM

O LLM resolveria essas 1.187 caixas — ele lê o rótulo sem dificuldade. Mas seria
errado, por três motivos:

1. **Paga por registro** o que uma correção resolve uma vez, para sempre.
2. **Não é reproduzível** — a banca vai pedir para rodar de novo.
3. **Apaga o sinal** de que a regra está ruim.

É a mesma armadilha do embedding, em que já caímos uma vez: usar a camada cara
para compensar a camada barata estar mal feita, em vez de consertar a barata.

---

## 7. A ordem correta

```
0  PAR ROTULADO        le 'DIAMETRO INTERNO: 39MM' direto        <- FALTANDO
1  LISTA DO PDM        valor permitido aparece literal
2  DICIONARIO CURADO   sinonimo de dominio
3  DICIONARIO APRENDIDO o que LLM/BERT ja resolveram
4  GRAMATICA           so onde NAO ha rotulo
5  BERT                recorta o telegrafico
6  LLM                 so o residuo em conflito
```

Mais os dois consertos da seção 6: contar atributo opcional como concorrente de
família, e aplicar a restrição de domínio também a caixa opcional.

Expectativa (a confirmar por medição): resolve 1.187 conflitos, preenche caixas
que hoje ficam vazias à toa, e reduz o volume que vai ao LLM. Deve ser o maior
ganho isolado que resta, porque atinge 59,9% dos registros.

---

## 8. Onde cada coisa está no código

| Camada | Arquivo | Função |
|---|---|---|
| 0 par rotulado | `rotulos.py` | `pares()` — **existe, não está ligada** |
| 1 lista do PDM | `regras.py` | `ExtratorLexico._por_gazetteer` |
| 2 dicionário curado | `sinonimos.py` | `SINONIMOS`, `canonizar()` |
| 3 dicionário aprendido | `aprendizado.py` | `Aprendizado.consultar()` |
| 4 gramática | `regras.py` | `_por_gramatica`, `_uma_familia`, `_atribuir_por_dominio` |
| 5 BERT | `bert.py` | `ExtratorBert.prever()` |
| 6 LLM | `llm.py` | `DesempateLlm.desempatar()` |
| decisão | `arbitro.py` | `Arbitro._decidir` — compara camadas e define o estado |
| portão | `validador.py` | `Validador.valor` — recusa o que o PDM não aceita |

Para inspecionar um registro:

```bash
.venv/bin/python scripts/05_encaixotar.py --ver 16279976 --sem-embedding
.venv/bin/python scripts/00_ver_classe.py PDM004
```

E no `artefatos/catalogo_final.xlsx`, a aba `ANTES_DEPOIS` liga cada caixa ao
trecho da linha original que a originou.
