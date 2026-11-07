# Análise de mercado e do problema — Desafio 01

> **Como ler este documento.** Tudo marcado 🟢 foi **medido na base entregue** (23.554 registros,
> `01_base_materiais.csv`), é reproduzível pelos scripts em [`scripts/`](../scripts/) e não contém
> nenhuma premissa. Tudo marcado 🟡 é **premissa de negócio** declarada, com a conta aberta para ser
> contestada. Tudo marcado 🔴 **precisa de fonte externa** e está aqui como estrutura a preencher.
> Nenhum número 🟢 e 🟡 está misturado em nenhuma soma.

---

## 1. Sumário executivo

A Serra Azul tem **R$ 200,9 milhões** em estoque de materiais e um cadastro em que 79% das descrições
estão fora do padrão da própria empresa. 🟢

Disso, **R$ 36,6 milhões (18,2% do estoque) é ganho direto endereçável** — capital parado em código
redundante, estoque travado em item bloqueado e sobrepreço do mesmo item comprado por códigos
diferentes. Mais **R$ 9,5 milhões de base fiscal exposta** por NCM ausente ou divergente. 🟢

O número que define o projeto não é nenhum desses. É este: **o casamento de texto não encontra
nenhum dos dois clusters de duplicidade que o próprio briefing plantou na base.** Zero de dois. 🟢

É isso que separa este desafio de um exercício de *string matching* — e é a razão comercial pela
qual o problema continua aberto depois de vinte anos de MDM vendido ao mercado.

| | |
|---|---|
| Estoque total na base | **R$ 200.874.691,83** 🟢 |
| Ganho direto endereçável | **R$ 36.552.204,83** · 18,2% do estoque 🟢 |
| Base fiscal exposta | **R$ 9.473.743,75** · 4,7% do estoque 🟢 |
| Volume negociável em conjunto | **R$ 12.006.654,91** 🟢 |
| Valor endereçável por registro | **R$ 1.551,85** 🟢 |

---

## 2. Onde está o dinheiro (e por que isso muda a estratégia)

O valor do estoque é brutalmente concentrado, e **concentrado exatamente onde o cadastro é pior**:

| Grupo | Registros | Valor em estoque | % do valor |
|---|---:|---:|---:|
| **SOB01 Sobressalentes** | 7.673 | **R$ 166.605.843** | **82,9%** |
| VAL01 Válvulas | 1.342 | R$ 7.269.687 | 3,6% |
| MAN01 Mangueiras | 1.545 | R$ 6.251.987 | 3,1% |
| TUB01 Tubos e conexões | 1.717 | R$ 4.587.337 | 2,3% |
| ELE01 Material elétrico | 1.483 | R$ 3.458.003 | 1,7% |
| FIL01 Filtros | 937 | R$ 2.475.614 | 1,2% |
| *outros 9 grupos* | 8.857 | R$ 10.226.220 | 5,1% |

🟢 Fonte: `01_base_materiais.csv`, `ESTOQUE_ATUAL × PRECO_MEDIO_UNITARIO`.

**A leitura que importa:** `SOB01` + `FIL01` são **8.610 registros (37% da base) e 84,1% do valor**.
São também as duas únicas classes em que o PDM define identidade por **fabricante + part number**
(regras 9 e 10) — e **61,4% desses 8.610 registros não têm fabricante ou não têm part number**. 🟢

> O dinheiro está, quase inteiro, na fatia da base onde a chave de identidade da própria empresa é
> impossível de calcular. **R$ 102,9 milhões de estoque estão em registros cegos.** 🟢

Isso não é uma curiosidade: é a definição do escopo do MVP. Atacar `FIX01` (4.516 registros,
R$ 688 mil, 0,3% do valor) é tecnicamente mais fácil e **economicamente irrelevante**.

---

## 3. Os quatro custos, quantificados

O briefing nomeia quatro custos. Todos os quatro são mensuráveis na base entregue.

### 3.1 Capital parado — R$ 3,94 milhões (piso) 🟢

620 clusters de duplicidade, 1.271 códigos envolvidos, **651 códigos redundantes** (2,8% da base).
O estoque desses 651 códigos deveria estar num código só.

**Este número é um piso, e um piso baixo** — ver seção 4.

### 3.2 Compra fragmentada — R$ 12,0 milhões negociáveis 🟢

**493 dos 620 clusters (79,5%) têm códigos em dois ou mais centros diferentes.** A mesma peça é
comprada separadamente pela mina, pela usina e pelo terminal, cada uma com seu código, cada uma
negociando o seu volume.

O caso mais caro da base: braço de suspensão **Caterpillar 8869005**, três códigos ativos —
um no Terminal Portuário, um na Mina Serra Azul, um no CD Central — **R$ 1.735.077 em estoque**. 🟢

Além do volume perdido, há sobrepreço medido: **R$ 1.190.126 de dispersão de preço** — a diferença
entre o que foi pago e o menor preço já praticado para o mesmo item, dentro do mesmo cluster. 🟢

### 3.3 Operação parada — 307 clusters em risco 🟢

**307 clusters têm um código com saldo e outro código zerado.** É a configuração exata do problema
descrito no briefing: a manutenção consulta o código que conhece, encontra zero, abre requisição de
compra, e a peça está no almoxarifado sob outro código.

O custo aqui não é o da peça — é o da hora de equipamento parado, que a base não contém. 🟡
A conta precisa do custo-hora de indisponibilidade de cada ativo, que é dado da empresa.

### 3.4 Risco fiscal — R$ 9,47 milhões de base exposta 🟢

| | Registros | Valor em estoque |
|---|---:|---:|
| NCM ausente | 1.173 | R$ 8.551.720 |
| NCM divergente da regra da classe | 563 | R$ 922.023 |
| **Base exposta** | **1.736** | **R$ 9.473.744** |
| NCM fora do formato `0000.00.00` | 8.480 | *(formato, não classificação)* |

🟢 Divergência apurada contra o conjunto de NCMs válidos por grupo, extraído das abas `CLASSES` e
`NCM_REFERENCIA` do PDM. **Nota metodológica:** este critério é permissivo — aceita qualquer NCM
que o PDM admita para aquele grupo. Um critério por *classe* (e não por grupo) elevaria a contagem,
e é o que o MVP vai produzir. Os 8.480 registros fora de formato não entram na soma porque formato
errado não é imposto errado — mas travam conferência de nota no recebimento.

---

## 4. O achado central: por que o casamento de texto não resolve

Esta seção é a tese do produto, e é a parte da análise que vale o pitch.

### 4.1 O teste contra o gabarito

O briefing plantou **dois clusters de duplicidade deliberados** nos últimos 15 registros da base:
três rolamentos 6205 vedados folga C3 (SKF, FAG, NSK) e três 6310 (SKF, FAG, NTN), mais o conjunto
de filtros.

Rodamos o casamento de texto por saco de palavras — normalizando caixa, acento e pontuação, dentro
do mesmo grupo de mercadoria — sobre a base inteira:

```
clusters de duplicidade encontrados entre os 15 produtos reais:  0
```
🟢

**Zero.** E não melhora com normalização pesada. Aplicamos a camada completa de normalização
determinística — expansão de 28 abreviações, tabela DN↔polegada (`DN 50 → 2POL`), sinônimos de aço
(`AISI 316 ≡ INOX 316 ≡ A4 ≡ SS316`), vedação de rolamento (`2RSH ≡ DDU ≡ 2HRS`), conversão psi→bar,
desmembramento `M12X50 → M12 + 50MM`. O resultado:

| | Texto ingênuo | Texto normalizado |
|---|---:|---:|
| Clusters | 620 | 621 |
| Códigos redundantes | 651 | 652 |
| Capital detectado | R$ 3.942.589 | R$ 4.165.093 |

🟢 **Ganho: +0,2%.** Catorze clusters novos, R$ 222 mil.

Normalizar o texto não resolve, porque o problema não é ortográfico. `ROL 6205-2RSH/C3 SKF` e
`ROLAMENTO FAG 6205-C-2HRS-C3` descrevem o mesmo rolamento com conjuntos de palavras genuinamente
diferentes. Nenhuma comparação de texto — exata, normalizada ou difusa — fecha esse par sem também
fechar pares errados.

### 4.2 O que funciona, medido

Nas classes em que o PDM define identidade por **fabricante + part number**, essa chave é computável
hoje, sem LLM, nos registros que têm os dois campos preenchidos:

| | |
|---|---:|
| Registros `SOB01`+`FIL01` com fabricante **e** part number | 3.320 |
| Chaves com mais de um código | 258 |
| **Códigos redundantes** | **283** |
| **Taxa de duplicidade** | **8,5%** |
| Capital parado | **R$ 3.184.119** |

🟢

**Leia essas duas linhas juntas:**

- Casamento de texto, base inteira (23.554 registros): **2,8%** de redundância.
- Chave de identidade do PDM, só onde é calculável (3.320 registros): **8,5%** de redundância.

A chave de identidade encontra **três vezes mais duplicidade**, numa fatia **sete vezes menor** da
base. E encontra R$ 3,18 milhões de capital parado em 3.320 registros — quase o mesmo que o texto
encontra em 23.554.

### 4.3 O valor que ninguém consegue ver hoje

A chave do PDM só fecha onde há fabricante e part number. Faltam em **5.290 dos 8.610** registros
das classes de referência — e esses registros carregam **R$ 102.956.199 de estoque**. 🟢

Nesses, o part number existe: está **dentro do texto da descrição**, não no campo. Os próprios 15
produtos reais do briefing provam isso — todos os 15 têm `REFERENCIA_FABRICANTE` **vazio**, com o
part number escrito na descrição (`FILTRO P551808 DONALDSON`). 🟢

Extrair o part number do texto e colocá-lo no campo certo é precisamente o trabalho do MVP.

> **Estimativa do teto.** Se a taxa de 8,5% medida nos registros com chave calculável se mantiver nos
> 5.290 registros cegos: **~451 códigos redundantes adicionais** e **~R$ 8,78 milhões** de capital
> parado adicional. 🟡
>
> *Premissa:* que a duplicidade se distribua igualmente entre registros bem e mal cadastrados.
> Essa premissa é provavelmente **conservadora** — registro mal cadastrado é mais fácil de duplicar,
> porque quem procura não acha. Mas é premissa, e está marcada como tal.

Somando o medido (R$ 3,18 M na fatia visível) com o estimado (R$ 8,78 M na fatia cega), a
duplicidade só nas classes de referência fica na ordem de **R$ 12 milhões** — contra os R$ 3,9 M que
o casamento de texto consegue enxergar. 🟡

**Convergência externa:** a faixa de 5% a 15% de registros duplicados em cadastro de materiais não
gerenciado é um número repetido na literatura de MDM industrial; os 8,5% medidos aqui caem no meio
dela. 🔴 *Precisa de citação antes do pitch — ver seção 10.*

---

## 5. O problema não é um passivo, é um fluxo

A tentação é tratar isso como mutirão de limpeza. Os dados dizem o contrário.

| | |
|---|---:|
| Período de cadastro na base | 2004 → 2026 (23 anos) 🟢 |
| Usuários distintos que cadastraram | **260** 🟢 |
| Média de cadastros novos por ano | **1.024** 🟢 |
| Cadastros de 2022 em diante | 4.933 🟢 |
| 2021 / 2022 / 2023 / 2024 / 2025 | 1.046 / 1.015 / 1.060 / 989 / 1.044 🟢 |

**A taxa de entrada é constante há cinco anos.** Não há sinal de desaceleração, de melhoria de
processo, de aprendizado. Duzentos e sessenta pessoas cadastrando, cada uma do seu jeito, mil itens
novos por ano.

E a fila de entrada tem forma conhecida:

| Pedidos de cadastro no período | 520 🟢 |
|---|---:|
| Com anexo para ler à mão | 136 (26%) 🟢 |
| Urgência ALTA ou EMERGENCIAL | 156 (30%) 🟢 |
| Canais distintos | PORTAL 279 · EMAIL 156 · PLANILHA 85 🟢 |
| Áreas solicitantes | 12 🟢 |

Três canais, doze áreas, um terço urgente, um quarto com anexo. É um processo manual sob pressão —
a condição exata que produz cadastro ruim.

**Consequência comercial, e é a mais importante deste documento:**

> Saneamento é **projeto**: acontece uma vez, tem fim, e o comprador natural é CAPEX ou consultoria.
> Cadastro é **operação**: acontece mil vezes por ano, para sempre, e o comprador natural é
> licença recorrente.
>
> Um sistema que só saneia a base entrega R$ 36,6 milhões uma vez e a base volta a se degradar a
> 1.024 itens/ano. Um sistema que também **barra a duplicata na porta de entrada** protege o ganho.
> O valor do saneamento é o gancho de venda; o valor do controle de entrada é o contrato.

---

## 6. Dimensionamento de mercado

### 6.1 A métrica portável

Contar empresas é frágil. A métrica que viaja entre empresas é a razão medida aqui:

```
valor endereçável  =  18,2% do valor do estoque de materiais        🟢
                   =  R$ 1.551,85 por registro de cadastro          🟢
```

Qualquer empresa industrial que informe o valor do seu estoque de materiais tem, por essa razão, uma
estimativa de primeira ordem do seu próprio ganho. É assim que o pitch deve dimensionar o cliente na
frente do cliente — não com um número de relatório de analista, mas com o número dele.

**Ressalva honesta:** 18,2% é a razão de **uma** base, e 15,6 dos 18,2 pontos vêm de estoque travado
em item bloqueado/obsoleto — que é um sintoma de governança de cadastro, mas também de política de
baixa de estoque, que o MVP não resolve sozinho. A razão mais defensável para um ganho atribuível
exclusivamente ao saneamento é a de **duplicidade + sobrepreço: 2,6% do estoque medido, e da ordem
de 6% no teto estimado**. 🟢🟡

### 6.2 Mercado endereçável (estrutura)

O perfil do cliente é nítido e derivado da base: operação industrial **multiplanta** (a duplicidade
nasce do centro), com **cadastro de materiais acima de ~10 mil itens**, **estoque de sobressalentes
de equipamento pesado** (é onde está 83% do valor) e **obrigação fiscal de NCM** (operação no
Brasil).

Setores que satisfazem o perfil: mineração, energia (geração e transmissão), óleo e gás, siderurgia,
celulose e papel, saneamento, cimento, química, açúcar e álcool.

```
TAM  =  Nº de empresas no perfil  ×  estoque médio de materiais  ×  2,6%–6%
```

🔴 **Os dois primeiros fatores exigem fonte externa e não estão disponíveis nesta sessão**
(sem acesso a busca web). Esta é a tabela a preencher antes do pitch:

| Fator | Onde buscar | Status |
|---|---|---|
| Nº de mineradoras com operação multiplanta no BR | ANM — Anuário Mineral Brasileiro; IBRAM | 🔴 a preencher |
| Nº de agentes de geração/transmissão | ANEEL — SIGA / Agentes Regulados | 🔴 a preencher |
| Estoque médio de materiais por empresa | Notas explicativas de ITR/DFP de B3 (conta "Estoques — materiais de manutenção") | 🔴 a preencher |
| Tamanho do mercado de MDM/PIM | Gartner, Forrester, IDC, MarketsandMarkets | 🔴 a preencher |
| Custo-hora de parada em mineração | benchmark setorial | 🔴 a preencher |

**Não inventamos esses números.** Um TAM fabricado é a coisa mais fácil de derrubar numa banca que
tem gente de suprimentos na mesa. A posição defensável é: *"o ganho medido nesta base é R$ 36,6
milhões; a razão é 18,2% do estoque; multiplique pelo seu estoque."*

### 6.3 SOM — o que o MVP alcança neste desafio

Aqui não há premissa: o alvo é a própria base.

| Fatia | Registros | Valor em estoque |
|---|---:|---:|
| `SOB01` + `FIL01` (identidade por fabricante+part#) | 8.610 | R$ 169.081.458 |
| ...dos quais cegos (sem fabricante ou part#) | 5.290 | R$ 102.956.199 |
| `VAL01`+`MAN01`+`TUB01`+`ELE01` (especificação técnica, alto valor) | 6.087 | R$ 21.567.014 |

🟢 Dois grupos — `SOB01` e `FIL01` — entregam 84% do valor. **O MVP deve atacar o critério de
identidade por fabricante + part number primeiro**, não as classes com schema mais bonito.

> Nota de divergência com o plano de projeto: [`02-plano-projeto.md`](02-plano-projeto.md) propõe a
> fatia vertical em `FIX01`+`VED01`+`ROL01` (6.851 registros, 29% da base) por regularidade técnica.
> Essa fatia vale **R$ 4,07 milhões — 2,0% do valor do estoque**. Faz sentido como fatia de
> *engenharia* (valida o pipeline rápido), mas **não pode ser a fatia do pitch**. O slide de
> resultado precisa de `SOB01`.

---

## 7. Panorama competitivo

### 7.1 Com o que a solução realmente compete

| Alternativa | O que é | Por que não resolveu |
|---|---|---|
| **Fazer nada** (o concorrente real) | conviver com a bagunça | o custo é difuso e não aparece em nenhuma linha de P&L; ninguém é demitido por duplicidade de cadastro |
| **Mutirão de planilha** | equipe interna limpando em Excel | 23.554 registros × 5 atributos; não escala, não se repete, e a base volta a sujar a 1.024 itens/ano 🟢 |
| **Consultoria de MDM** | projeto de saneamento com equipe alocada | resolve o passivo e vai embora; não barra a entrada; custo por registro alto |
| **Módulo de governança do ERP** (SAP MDG e equivalentes) | workflow de aprovação de cadastro | garante que o campo foi *preenchido*, não que está *correto*; não extrai atributo de texto livre; não detecta duplicidade semântica |
| **Ferramenta de PIM/MDM** (Informatica, Stibo, Semarchy e afins) | plataforma de dado mestre | o motor de *matching* é de similaridade de texto e regra configurada à mão — exatamente o que falha nos 0/2 do gabarito 🟢 |
| **BPO de cadastro** | terceirizar o cadastramento | transfere o custo, mantém a inconsistência; e o fornecedor não tem o PDM do cliente |

### 7.2 Onde está a brecha

A tecnologia de MDM é madura — duas décadas de produto. O problema continua aberto porque todas
essas ferramentas pressupõem **o dado já estruturado em campos**. Elas governam, versionam,
aprovam e casam registros. Nenhuma delas **lê `FILTRO P551808 DONALDSON` e entende que `P551808`
é um part number e `DONALDSON` é um fabricante**.

Esse passo — texto livre industrial em português abreviado → atributos tipados contra um padrão
fechado — não era viável a custo razoável antes dos modelos de linguagem atuais. Era trabalho de
especialista humano, e por isso ficava sem fazer.

### 7.3 Posicionamento

> Não é uma ferramenta de MDM. É a **camada de extração que falta na frente** de qualquer MDM:
> transforma texto industrial sujo em atributos tipados, e só então deixa a chave de identidade
> decidir duplicidade.

Três diferenciais, todos verificáveis na base:

1. **Identidade por chave, não por similaridade.** Dois códigos são o mesmo item porque *todos* os
   atributos obrigatórios coincidem — afirmação auditável, reproduzível e explicável lado a lado na
   tela. Similaridade de texto erra 2 de 2 no gabarito. 🟢
2. **Equivalência ≠ duplicidade** (regra 13 do PDM). `CAT 1R-1808` e `DONALDSON P551808` são
   intercambiáveis e **itens distintos**; unificar os dois corrompe o cadastro. Um algoritmo de
   similaridade erra exatamente aí. Acertar isso é o que distingue um sistema de um script.
3. **Pendência como saída legítima.** Atributo obrigatório ausente vira devolução com a lista exata
   do que falta — não um palpite. É o que torna o sistema utilizável por quem assina o cadastro.

---

## 8. Por que agora

| Fator | Evidência |
|---|---|
| **Custo de extração caiu** | 23.554 registros × ~5 atributos é escala viável com modelo de linguagem, com cache e caminho determinístico para os casos fáceis |
| **Saída estruturada ficou confiável** | *tool use* / structured output com JSON Schema por classe força o modelo a devolver só valores do `enum` — elimina alucinação de formato por construção |
| **O padrão já existe** | o PDM é um contrato fechado e **executável**: 44 classes, 229 atributos, listas de valores, 13 regras. Não é preciso inventar taxonomia — só cumpri-la 🟢 |
| **Infraestrutura pronta** | AWS Bedrock configurado; nada a provisionar |
| **Pressão fiscal crescente** | a reforma tributária (CBS/IBS) aumenta a consequência de classificação errada; 1.736 registros já expostos nesta base 🟢 |

O ponto central: **o PDM transforma o problema de aberto em fechado.** Sem padrão, extrair atributo
de texto industrial é tarefa sem gabarito. Com padrão, é tarefa com schema, vocabulário controlado e
critério de identidade definido — ou seja, mensurável. É por isso que o problema é resolvível agora
e não era antes.

---

## 9. Modelo de negócio

### 9.1 Duas receitas, porque são dois problemas

| | Saneamento (passivo) | Cadastro (fluxo) |
|---|---|---|
| Natureza | projeto, uma vez | operação, contínua |
| Volume nesta base | 23.554 registros 🟢 | 1.024 itens/ano 🟢 |
| Entrega | base padronizada, duplicidades unificadas, NCM corrigido | pedido → aprovado / já existe / devolvido / fora do PDM |
| Valor ancorado em | R$ 36,6 M de ganho direto 🟢 | proteger o ganho + custo de cadastro evitado |
| Receita | preço por registro processado, ou % do capital liberado | licença recorrente por volume de pedidos |

A precificação por **% do capital liberado** é a mais forte comercialmente — alinha o fornecedor ao
resultado e dispensa discussão de custo de software — e é possível justamente porque o ganho é
**medido na base do cliente antes de contratar**: o placar antes/depois já está calculado.

### 9.2 O número que vende

Dos R$ 36,6 milhões, o que realmente converte é a linha mais concreta: **um braço de suspensão
Caterpillar com três códigos ativos em três centros, R$ 1,74 milhão em estoque.** 🟢

Não é um indicador agregado. É uma peça, três códigos, um número. Isso é o slide.

---

## 10. Riscos e limitações desta análise

| Risco | Avaliação |
|---|---|
| **Empresa fictícia** | a base é sintética; as proporções são plausíveis e internamente consistentes, mas não são de uma empresa real. Todo número 🟢 vale *nesta base* — a transposição para o mercado real depende da seção 6.2, que está 🔴 |
| **R$ 36,6 M inclui estoque travado** | 15,6 dos 18,2 pontos percentuais são itens bloqueados/obsoletos com saldo. Isso é *capital identificado*, não *economia gerada* — baixar estoque é decisão de política contábil. **No pitch, separar**: R$ 5,1 M de duplicidade + sobrepreço (atribuível ao MVP) vs. R$ 31,4 M de estoque travado (que o MVP *revela*) |
| **Teto de duplicidade é estimativa** | os ~R$ 8,8 M adicionais dependem da premissa de taxa constante (seção 4.3). O MVP produz o número real — e a análise deve ser **reescrita com ele** antes da apresentação |
| **Divergência de NCM depende do critério** | 563 pelo critério por grupo; a documentação interna reporta 1.737 por critério mais estrito. Ambos defensáveis, critérios diferentes. **Declarar qual se usa** |
| **Sem fontes de mercado externas** | TAM, benchmarks setoriais e tamanho do mercado de MDM estão 🔴. Esta sessão não tem acesso a busca web |
| **Custo de parada não quantificado** | o custo mais alto dos quatro (operação parada) é o único que a base não permite calcular. 307 clusters em risco está medido 🟢; o valor em reais exige custo-hora de indisponibilidade 🟡 |

### Pendências antes do pitch

1. 🔴 Preencher a tabela de fontes da seção 6.2 (ANM, ANEEL, B3, Gartner).
2. 🔴 Citar a faixa de 5–15% de duplicidade em cadastro não gerenciado, ou remover a afirmação.
3. 🟡 Obter custo-hora de parada para monetizar os 307 clusters em risco.
4. 🟢 **Reexecutar esta análise com a saída real do MVP** — substituir o teto estimado pelo medido.
   É a única pendência que muda a conclusão, e para melhor: todo número aqui é piso.

---

## 11. Conclusão

O mercado de ferramentas de dado mestre tem vinte anos e o problema continua aberto. A análise desta
base mostra por quê, com um número: **o casamento de texto — a tecnologia sobre a qual essas
ferramentas foram construídas — erra 2 de 2 nos casos de duplicidade do gabarito.** 🟢

O que mudou não foi a necessidade. Foi a viabilidade: extrair atributo tipado de texto industrial
abreviado passou a custar pouco, e o PDM fornece o gabarito contra o qual medir. Com os dois,
duplicidade deixa de ser problema de processamento de linguagem e vira **igualdade de chave** —
reproduzível, auditável, defensável na frente de quem assina o cadastro.

Nesta base isso vale **R$ 36,6 milhões identificados**, dos quais R$ 5,1 milhões diretamente
atribuíveis ao saneamento hoje e uma ordem de R$ 13 milhões quando os R$ 102,9 milhões de registros
cegos forem lidos. 🟢🟡

E vale **1.024 vezes por ano, para sempre**, na porta de entrada — que é onde está o contrato. 🟢

---

### Reprodutibilidade

```bash
python3 -I scripts/analise_mercado.py      dados/01_base_materiais.csv dados/03_padrao_cadastro_PDM.xlsx
python3 -I scripts/analise_normalizacao.py dados/01_base_materiais.csv dados/02_pedidos_cadastro.csv
python3 -I scripts/analise_teto.py         dados/01_base_materiais.csv
```

Todos os números 🟢 deste documento saem desses três scripts. Nenhum depende de serviço externo,
de modelo de linguagem ou de premissa.
