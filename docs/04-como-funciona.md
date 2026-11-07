# Como o pipeline funciona, do zero

Este documento explica a solução inteira sem pressupor nada. Se você só vai ler
um arquivo, leia este.

A ideia cabe em uma frase: **transformar cada linha de texto numa grade de
caixas; quando duas grades têm as mesmas caixas, é o mesmo item.** Todo o resto
é consequência disso.

---

## 1. O problema

A empresa tem 23.554 materiais cadastrados. O mesmo item foi cadastrado várias
vezes, por pessoas diferentes, ao longo de 22 anos, cada uma escrevendo do seu
jeito. Exemplo real da base:

```
16220310   PARAFUSO SEXTAVADO, ROSCA:ROSCA GROSSA, ROSCA:M12, COMPRIMENTO:75,0MM, GRAU:8.8, MAT:ACO CARBONO...
16686120   PARAFUSO SEXTAVADO; ROSCA: METRICA GROSSA; BITOLA: M12; COMPRIMENTO: 75MM; CLASSE RESISTENCIA: 8.8...
```

É **o mesmo parafuso**. Dois códigos, dois estoques, duas compras. A empresa
compra num código enquanto sobra no outro, e a manutenção procura um e não
encontra o outro.

Um computador olhando esses dois textos vê strings diferentes. E comparar texto
não resolve: `GRAU:8.8` e `CLASSE RESISTENCIA: 8.8` dizem a mesma coisa com
palavras diferentes, enquanto `ACO INOX 304` e `ACO INOX 316` são quase o mesmo
texto e são itens distintos.

**É por isso que a comparação não pode ser feita no texto. Tem que ser feita
depois de organizar o texto.**

---

## 2. A ideia central: caixas

Em vez de comparar frases, a gente quebra cada frase numa **grade de caixas**.
Uma caixa por característica do item.

```
                 ┌──────────────────────────────────────────┐
LINHA CRUA  ──►  │  PARAF SEXT ROSCA MA BITOLA M8           │
                 │  COMPRIMENTO 35MM 10.9 MATERIAL ACO CARB │
                 │  ACAB ZA NORMA DIN 933                   │
                 └──────────────────────────────────────────┘
                                   │
                                   ▼
                 ┌──────────────────────────────────────────┐
GRADE       ──►  │ SUJEITO            PARAFUSO SEXTAVADO    │
DE CAIXAS        │ ROSCA              METRICA GROSSA        │
                 │ BITOLA             M8                    │
                 │ COMPRIMENTO        35MM                  │
                 │ CLASSE RESISTENCIA 10.9                  │
                 │ MATERIAL           ACO CARBONO           │
                 │ ACABAMENTO         ZINCADO AMARELO       │
                 │ NORMA              DIN 933               │
                 └──────────────────────────────────────────┘
```

Repare no que aconteceu: `ACO CARB` virou `ACO CARBONO`, `ZA` virou
`ZINCADO AMARELO`, `PARAF SEXT` virou `PARAFUSO SEXTAVADO`. O texto foi
**padronizado dentro de cada caixa**.

Agora duas linhas escritas de jeitos diferentes produzem grades **idênticas** — e
comparar grades idênticas é trivial.

### Quem define quais caixas existem

Não fomos nós. A empresa tem um documento chamado **PDM** (Padrão Descritivo de
Materiais), que é a planilha `03_padrao_cadastro_PDM.xlsx`. Ele diz:

- quais **classes** de material existem (44: parafuso sextavado, retentor, válvula esfera, filtro...);
- quais **caixas** cada classe tem (229 atributos no total);
- quais **valores** cada caixa aceita (ex.: MATERIAL de um parafuso só pode ser `ACO CARBONO`, `ACO INOX 304` ou `ACO INOX 316`);
- em que **ordem** as caixas aparecem na descrição final.

O PDM é lido da planilha em tempo de execução, nunca digitado no código. Se a
empresa mudar o padrão, o pipeline continua valendo.

---

## 3. Os três tipos de caixa (e por que isso importa muito)

Nem toda caixa se preenche do mesmo jeito. Classificar o tipo da caixa é a
decisão mais importante do projeto.

### Caixa TEXTUAL — tem lista de valores

```
MATERIAL  ->  aceita apenas: ACO CARBONO | ACO INOX 304 | ACO INOX 316
```

Como o PDM dá a lista fechada, preencher é **procurar qual valor da lista
aparece no texto**. É busca em dicionário, não é adivinhação. 74,9% dos
atributos obrigatórios do PDM são assim.

### Caixa NUMERICA — tem formato fixo

```
COMPRIMENTO  ->  numero + MM, decimal com virgula (ex.: 16,25MM)
PRESSAO      ->  numero + BAR  (se vier em psi, converte: dividir por 14,5038)
DIAMETRO     ->  fracao + POL  (1/2POL, 1.1/4POL)
```

Preenche com expressão regular e converte a unidade. **Nunca usa modelo de
inteligência artificial aqui**, e isso é deliberado: trocar `110MM` por `15MM`
cria um item errado na base.

### Caixa LIVRE — não tem lista nem formato

```
REFERENCIA FABRICANTE  ->  '1R-1808', 'MM2905816', '6205-2RS/C3'
MODELO EQUIPAMENTO     ->  'HP400', '785D'
```

É o código da peça no catálogo do fabricante. Não existe lista para conferir nem
formato para casar. **Esta é a caixa difícil**, e falaremos dela na seção 8.

---

## 4. Passo 1 — descobrir o sujeito

Antes de preencher caixa alguma, precisamos saber **de qual classe o item é**,
porque é a classe que define quais caixas existem. Um parafuso tem 7 caixas; um
retentor tem 5; um filtro tem 6, e completamente diferentes.

O "sujeito" é o `SUBSTANTIVO + QUALIFICADOR` da classe: `PARAFUSO SEXTAVADO`,
`VALVULA ESFERA`, `ANEL O-RING`.

Como achamos: a base já traz uma coluna `GRUPO_MERCADORIA` (FIX01 = fixadores,
VED01 = vedações, ...) preenchida em 100% dos registros. Isso reduz 44 classes a
1–3 candidatas. Depois é casar o substantivo no texto.

```
texto: "PARAF SEXT ROSCA MA BITOLA M8 ..."
grupo: FIX01  ->  candidatas: PARAFUSO SEXTAVADO, PARAFUSO SEXTAVADO INTERNO,
                              PORCA, ARRUELA LISA, ARRUELA PRESSAO, BARRA ROSCADA
expande abreviacao: PARAF -> PARAFUSO,  SEXT -> SEXTAVADO
casa: "PARAFUSO SEXTAVADO"  ->  classe PDM001
```

**Resultado medido: 97,0% das linhas recebem uma classe.** As 3,0% restantes
(718 registros) não têm classe no PDM — como o pedido real de *"cadeira de
escritório giratória para a sala de controle"*. Essas são marcadas
`FORA_DO_PDM`, nunca forçadas numa classe errada.

Dois detalhes que custaram bug:

- O grupo da base às vezes está **errado**. O item `12711820` é um retentor
  cadastrado em TUB01 (tubos). Quando nenhuma classe do grupo casa, procuramos
  nas 44 e marcamos `grupo_corrigido` — corrigir o grupo é entregável.
- `ELEMENTO FILTRANTE OLEO FLEETGUARD LF3970` virava **óleo lubrificante**,
  porque a palavra `OLEO` casava e nenhuma classe de filtro casava literalmente.
  Resolvido com sinônimo de substantivo (`ELEMENTO FILTRANTE` → `FILTRO`).

---

## 5. Passo 2 — preencher as caixas, do barato para o caro

Cada caixa passa por uma cascata. A ordem foi definida por medição, não por
gosto. Para cada camada: se resolveu, para; se não, desce.

```
  ┌─ 1. CASAMENTO LITERAL ─────────────────────────────────────────┐
  │  O valor da lista aparece no texto? 'DIN 933' está lá.         │
  │  custo zero · sempre certo · resolve a maioria                 │
  └────────────────────────────────────────────────────────────────┘
                              │ não resolveu
  ┌─ 2. DICIONÁRIO DE DOMÍNIO ─────────────────────────────────────┐
  │  'ACO CARB' -> ACO CARBONO ;  'ZA' -> ZINCADO AMARELO          │
  │  'AISI 316' -> ACO INOX 316 ;  'NITRILICA' -> NBR              │
  │  custo zero · conhecimento de engenharia escrito à mão         │
  └────────────────────────────────────────────────────────────────┘
                              │
  ┌─ 3. GRAMÁTICA (só caixa NUMERICA) ─────────────────────────────┐
  │  '35MM' -> 35MM ;  '1960 psi' -> 135,1BAR ;  'DN 50' -> 2POL   │
  │  'M12X50' -> BITOLA M12 + COMPRIMENTO 50MM  (regra 2 do PDM)   │
  └────────────────────────────────────────────────────────────────┘
                              │
  ┌─ 4. BERT  (ainda não treinado) ────────────────────────────────┐
  │  RECORTA qual trecho do texto pertence a qual caixa.           │
  │  É a única camada que resolve caixa LIVRE.                     │
  └────────────────────────────────────────────────────────────────┘
                              │
  ┌─ 5. EMBEDDING ─────────────────────────────────────────────────┐
  │  Compara o trecho recortado com a lista por similaridade.      │
  │  Só funciona se receber um trecho limpo (depende do passo 4).  │
  └────────────────────────────────────────────────────────────────┘
                              │
  ┌─ 6. LLM ───────────────────────────────────────────────────────┐
  │  Só nas caixas que sobraram em dúvida. Ver seção 7.            │
  └────────────────────────────────────────────────────────────────┘
```

De onde vêm os valores hoje, medido na base inteira:

| Camada | Caixas preenchidas | % |
|---|---|---|
| casamento literal (lista do PDM) | 57.615 | 68,4% |
| gramática (grandezas) | 13.311 | 16,8% |
| regra 2 do PDM (`M12X50`) | 6.456 | 8,1% |
| coluna do ERP (`FABRICANTE`) | 4.862 | 5,8% |
| restrição de domínio / ordem | 2.046 | 2,6% |

Ou seja: **mais de 90% das caixas são preenchidas por regra determinística**,
sem modelo nenhum. Essa é a razão de o LLM não ser a primeira camada.

### A restrição de domínio: um truque que vale mais que modelo

A classe RETENTOR tem três caixas, todas em milímetro:
`DIAMETRO EIXO`, `DIAMETRO ALOJAMENTO`, `LARGURA`. O texto diz:

```
RETENTOR ... 90MM ... 112MM ... 8MM
```

Qual número vai em qual caixa? Nenhuma regra de texto sabe. Mas **engenharia
sabe**: o alojamento é sempre maior que o eixo, que é maior que a largura. Então
ordenamos: 112 → alojamento, 90 → eixo, 8 → largura. Certo, determinístico, e
nenhum modelo foi usado.

Funciona em 782 registros da base. Em outros 397 não funciona, porque o texto
traz menos números do que caixas — é o caso do passo 4.

---

## 6. Passo 3 — as bandas de confiança

Nem todo preenchimento merece a mesma confiança. Cada caixa recebe uma **banda**:

| Banda | Significa | O que acontece |
|---|---|---|
| **EXATA** | o valor da lista estava escrito no texto | aceita, sem LLM |
| **ALTA** | similaridade alta **e** com folga sobre o segundo lugar | aceita, sem LLM |
| **BANDA_LLM** | parece bater, mas sem folga | **chama o LLM** |
| **BAIXA** | não bate com nada | pendência, nunca palpite |
| **VAZIA** | o texto não informa | pendência |

### Por que "folga" e não só similaridade

Isso é a parte menos óbvia e a mais importante. Medimos a distância entre
valores do próprio PDM com um modelo de embedding:

```
ACO INOX 304  x  ACO INOX 316   ->  0,963 de similaridade
ROSCA NPT     x  ROSCA BSP      ->  0,965
DIN 931       x  DIN 933        ->  0,959
150#          x  300#           ->  0,944
```

São pares que **nunca podem ser confundidos** e estão todos acima de 0,94. Logo,
"similaridade de 0,95" não prova nada sozinha. O que prova é a **margem**: a
distância entre o primeiro e o segundo colocado. Se os dois primeiros estão
empatados, a caixa vai para o LLM, mesmo com similaridade de 0,97.

E tem uma trava ainda mais forte, a **trava de gêmeo numérico**: se o primeiro e
o segundo colocados diferem apenas por um número (`304` vs `316`, `931` vs
`933`), o embedding **nunca** pode decidir, qualquer que seja a folga.

Isso não é paranoia. É o erro mais caro do domínio: trocar 304 por 316 cria um
item errado que alguém vai comprar e instalar.

---

## 7. Passo 4 — quando chamar o LLM

A regra é uma linha:

> **Se todas as caixas obrigatórias estão cheias e em banda EXATA ou ALTA, não
> chama o LLM. Se alguma está em BANDA_LLM, chama — só para aquelas caixas.**

```
          todas as caixas obrigatórias OK?
                    │
        ┌───────────┴────────────┐
       SIM                      NÃO
        │                        │
        ▼                        ▼
   segue direto         alguma em BANDA_LLM?
   para a junção          │            │
   (custo zero)          SIM          NÃO
                          │            │
                          ▼            ▼
                    chama o LLM   PENDENTE
                    só nas caixas  (dado não
                    em dúvida      está no texto)
```

**O caso PENDENTE não vai para o LLM, e isso é intencional.** Se a informação
não está no texto, nenhum modelo pode preenchê-la sem inventar. Medimos: 33% dos
atributos obrigatórios estão genuinamente ausentes da base. Os trechos que
sobram não são sinônimos — são coisas como `MATERIAL = 'NAO UTILIZAR'` e
`BITOLA = 'PARAFUSO SEXTAVADO'`, ou seja, texto errado na caixa. Um LLM ali
produz invenção plausível, que é o único erro que não podemos cometer.

Esses casos vão para **enriquecimento** (buscar em catálogo de fabricante, com
registro da fonte) ou **devolução ao solicitante**, não para extração.

### E o LLM tem passe livre?

Não. Toda proposta do LLM passa pelo mesmo validador das outras camadas: se o
valor não está na lista do PDM, é recusado. Vale para regra, para BERT, para
embedding e para o LLM, igualmente. É o que impede alucinação de chegar na base.

Hoje, medido: **15,2% dos registros** cairiam em alguma caixa de BANDA_LLM. Os
outros 84,8% se resolvem sem nenhuma chamada.

---

## 8. Passo 5 — a verificação de quando são iguais

Aqui a ideia das caixas dá o retorno. Depois que as caixas estão preenchidas e
padronizadas, **duplicidade deixa de ser semelhança e passa a ser igualdade**.

Monta-se uma **chave de identidade** concatenando a classe, o sujeito e o valor
de todas as caixas obrigatórias:

```
16220310  PARAFUSO SEXTAVADO, ROSCA:ROSCA GROSSA, ROSCA:M12, COMPRIMENTO:75,0MM, GRAU:8.8, MAT:ACO CARBONO...
16686120  PARAFUSO SEXTAVADO; ROSCA: METRICA GROSSA; BITOLA: M12; COMPRIMENTO: 75MM; CLASSE RESISTENCIA: 8.8...

  CAIXA                 16220310                16686120
  ------------------------------------------------------------------
 *ROSCA                 METRICA GROSSA          METRICA GROSSA
 *BITOLA                M12                     M12
 *COMPRIMENTO           75MM                    75MM
 *CLASSE RESISTENCIA    8.8                     8.8
 *MATERIAL              ACO CARBONO             ACO CARBONO
 *ACABAMENTO            OXIDADO PRETO           OXIDADO PRETO
 *NORMA                 DIN 931                 DIN 931

CHAVE (idêntica nos dois):
PDM001|PARAFUSO|ROSCA=METRICA GROSSA|BITOLA=M12|COMPRIMENTO=75MM|
CLASSE RESISTENCIA=8.8|MATERIAL=ACO CARBONO|ACABAMENTO=OXIDADO PRETO|NORMA=DIN 931
```

Mesma chave ⇒ mesmo item. E a justificativa cabe numa frase que qualquer pessoa
de suprimentos entende: *"são o mesmo item porque **todos** os atributos
obrigatórios coincidem"*. Nenhum modelo opinou. É reproduzível e auditável.

### Se falta uma caixa, a chave não fecha

Isso é por segurança: com `MATERIAL` vazio, não há como afirmar que dois
parafusos são iguais — podem ser um de aço carbono e um de inox. A chave devolve
"não sei" em vez de arriscar.

### Duas formas de identidade

O PDM define dois critérios, e eles são diferentes de propósito:

| Critério | Classes | Chave |
|---|---|---|
| **ESPECIFICAÇÃO TÉCNICA** | 42 classes (parafuso, válvula, cabo...) | classe + sujeito + **todos** os obrigatórios |
| **REFERÊNCIA DO FABRICANTE** | filtros e sobressalentes (37% da base) | classe + sujeito + **fabricante + part number** |

### A pegadinha que derruba solução ingênua

O PDM tem a regra 13: **equivalência não é duplicidade.**

```
CAT 1R-1808        e   DONALDSON P551808    -> filtros INTERCAMBIÁVEIS
                                               mas itens DISTINTOS
```

Eles se substituem na máquina, e por isso aparecem em texto parecido. Um
algoritmo de similaridade junta os dois e **erra**: são dois produtos de dois
fabricantes, com dois preços e dois contratos. A equivalência deve ser
*registrada*, nunca usada para juntar códigos.

Já a chave acerta sozinha, porque o fabricante faz parte dela.
Verificamos nos 15 produtos reais da base: **zero junções indevidas.**

### E o escolhido para sobreviver?

Em cada grupo de códigos iguais, um fica ativo e os outros são bloqueados. A
escolha segue uma regra explícita, sem critério subjetivo:

```
1. está ATIVO (ganha de BLOQUEADO/OBSOLETO)
2. tem mais caixas preenchidas
3. teve movimentação mais recente
4. tem mais valor em estoque
5. empate: o código mais antigo
```

Saída, no formato que o briefing pede:

```
18418581  ATIVO      BRACO SUSPENSAO; APLICACAO: CAMINHAO FORA DE ESTRADA;
                     MODELO EQUIPAMENTO: 785D; FABRICANTE: CATERPILLAR;
                     REFERENCIA FABRICANTE: 886-9005
10646730  BLOQUEADO · USAR 18418581
10236405  BLOQUEADO · USAR 18418581
```

---

## 9. Onde estamos hoje

Tudo abaixo está rodando, sem BERT e sem LLM — só as camadas determinísticas.

### Encaixotamento

```
linhas processadas ................. 23.554
receberam classe .................. 97,0%
caixas criadas .................... 15.552 (em 3.000 registros)

caixas obrigatórias por banda          por tipo de caixa
  EXATA      68,5%                       TEXTUAL   75,7% cheias
  BANDA_LLM   0,4%                       NUMERICA  71,9% cheias
  VAZIA      31,1%                       LIVRE      0,0% cheias  ◄── o buraco
```

### Estado dos registros

| Estado | Registros | % |
|---|---|---|
| SANEADO (todas as caixas obrigatórias cheias) | 6.810 | 28,9% |
| PENDENTE (falta dado que não está no texto) | 14.158 | 60,1% |
| REVISÃO (caixa em dúvida) | 1.868 | 7,9% |
| FORA_DO_PDM (sem classe) | 718 | 3,0% |
| **completude média das caixas obrigatórias** | | **0,721** |

### Junção

```
com chave de identidade fechada ....  8.000   34,0%
  chaves distintas ..................  7.124
  chaves com mais de um código ......    630
  CÓDIGOS REDUNDANTES ...............    876   3,7% da base

capital em código redundante ....... R$ 13,72 mi   (6,8% do estoque)
dispersão de preço do mesmo item ... R$  2,83 mi
valor negociável em conjunto ....... R$ 21,83 mi
clusters com risco de parada .......      379
```

Comparação: o `analise_mercado.py`, que compara texto por saco de palavras,
encontra ~651 códigos redundantes. A chave por caixas encontra 876, **e cada um
com justificativa auditável**.

### Honestidade sobre esses números

Eles já foram **maiores e estavam errados**. Durante a verificação encontramos
três bugs que inflavam o resultado:

1. Um regex de inteiro capturava o `35` de dentro de `35MM2` e o colocava em
   `NUMERO CONDUTORES`.
2. A chave de identidade ignorava os 19 atributos **obrigatórios condicionais**
   do PDM. Consequência: três cabos idênticos exceto pela cor (VERDE, AZUL,
   PRETO) fechavam a mesma chave e eram juntados.
3. O validador testava o formato `POL` antes de `MM` num atributo cujo formato
   cita os dois, e reescrevia `75MM` como `75POL` — trocando a medida do item.

Corrigidos, os redundantes caíram de **1.410 para 876**. Os 534 a menos eram
junções falsas. Existem três testes automatizados cobrindo exatamente esses
casos, para não voltarem.

---

## 10. O que falta, e é só uma coisa

Olhe de novo a linha que importa:

```
caixa LIVRE ....... 0,0% cheias   (1.131 caixas em 3.000 registros)
```

Caixa `LIVRE` é part number e referência de fabricante. Não tem lista para casar
nem formato numérico para extrair — **nenhuma regra alcança**. E ela é
exatamente o que falta para as junções de maior valor:

```
11315577  FILTRO OLEO 1R1808 CAT
            FABRICANTE: CATERPILLAR ✓    REFERENCIA FABRICANTE: <vazia>
            sobra: OLEO 1R1808 CAT            ↑ o dado está aqui!

29458054  FILTRO OLEO MOTOR CATERPILLAR 1R-1808
            FABRICANTE: CATERPILLAR ✓    REFERENCIA FABRICANTE: <vazia>
            sobra: OLEO MOTOR 1R-1808         ↑ o dado está aqui!
```

São o **mesmo filtro** (`1R1808` ≡ `1R-1808`). Falta **uma caixa** para a chave
fechar e eles juntarem. O part number está visível no campo `sobra`, que é o
diagnóstico de "texto que nenhuma caixa reivindicou".

Mesma história nos seis rolamentos 6205/6310 que o briefing plantou na base.

**É para isso que serve o BERT.** Ele não adivinha valor: ele **recorta** qual
trecho do texto pertence a qual caixa — e é a única camada capaz de preencher
caixa LIVRE. O treino está documentado em `docs/03-treinar-bert.md` e vai rodar
em outra máquina. Uma época de treino já deu F1 de 0,972.

Quando ele entrar, a expectativa é que a chave feche para boa parte dos 8.863
registros de classe de referência (hoje em 55,7%) — e esses são os de maior
valor unitário, sobressalentes e filtros. O ganho de junção não é incremental:
é onde está o capital.

---

## 11. Mapa dos arquivos

### O caminho dos dados

```
dados/03_padrao_cadastro_PDM.xlsx
   │  scripts/01_compilar_pdm.py
   ▼
artefatos/pdm.json          ← 44 classes, 229 caixas, listas de valores
   │
   │  dados/01_base_materiais.xlsx  (23.554 linhas)
   ▼
scripts/04_extrair.py       ← roda o pipeline inteiro
   ├─► artefatos/saneado_base.csv      uma linha por registro, com descrição no padrão
   └─► artefatos/decisoes_base.jsonl   trilha de auditoria: cada caixa, fonte e motivo
   │
   ▼
scripts/06_juntar.py        ← agrupa por chave e escolhe o sobrevivente
   └─► artefatos/plano_juncao.csv      código, ação, usar <código>
```

### Para ver uma grade de caixas

```bash
.venv/bin/python scripts/05_encaixotar.py --ver 12711820,11315577
```

### O código

| Arquivo | O que faz |
|---|---|
| `texto.py` | normaliza texto, converte unidade (psi→bar, DN→POL), desmembra `M12X50` |
| `pdm.py` | lê o PDM da planilha; decide quando atributo condicional se aplica |
| `caixas.py` | define a caixa, o tipo (TEXTUAL/NUMERICA/LIVRE) e as bandas |
| `regras.py` | camada 1 e 3: acha o sujeito, casa dicionário, aplica gramática |
| `sinonimos.py` | camada 2: conhecimento de domínio (`AISI 316` → `ACO INOX 316`) |
| `bert.py` | camada 4: recorte (a treinar) |
| `embeddings.py` | camada 5: similaridade com margem |
| `arbitro.py` | mede discordância e decide se escala para o LLM |
| `llm.py` | camada 6: Claude no Bedrock, só no resíduo |
| `validador.py` | **o portão**: nenhum valor entra sem obedecer ao PDM. Monta a chave de identidade |
| `encaixotador.py` | monta a grade de caixas de uma linha |
| `pipeline.py` | orquestra tudo |

### Testes

```bash
.venv/bin/python -m pytest tests/ -q      # 63 testes
```

Eles cobrem as invariantes do PDM (formato de unidade, lista de valores, chave de
identidade) e os casos reais do briefing: o rolamento 6205 que **deve** juntar,
o filtro intercambiável que **não** deve, e os três bugs de junção falsa da
seção 9.

---

## 12. Glossário

| Termo | Significado |
|---|---|
| **PDM** | Padrão Descritivo de Materiais: o documento da empresa que define o cadastro correto |
| **Caixa** | um atributo de um item; a célula da grade |
| **Grade** | todas as caixas de uma linha |
| **Sujeito** | `SUBSTANTIVO + QUALIFICADOR` da classe (`PARAFUSO SEXTAVADO`) |
| **Classe** | um dos 44 tipos de material do PDM, identificado por `PDM001`...`PDM110` |
| **Chave de identidade** | a concatenação das caixas obrigatórias; mesma chave = mesmo item |
| **Banda** | nível de confiança da caixa; define se chama o LLM |
| **Margem** | distância entre o 1º e o 2º valor mais parecido; o que realmente autoriza aceitar |
| **Sobra** | texto da linha que nenhuma caixa reivindicou; diagnóstico de recorte |
| **Gazetteer** | busca por dicionário: procurar no texto os valores da lista do PDM |
| **BIO** | esquema de rótulo do BERT: `B-` começo do valor, `I-` continuação, `O` fora |
| **Distant supervision** | treinar com rótulos tirados dos próprios dados, sem anotação manual |
| **NCM** | classificação fiscal do item, 8 dígitos; define imposto |
