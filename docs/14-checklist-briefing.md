# Checklist do briefing: o que existe, onde está e se foi medido

Data: 2026-11-07. Frente V3 do `docs/13-plano-validacao.md`.

Este documento cruza cada exigência do `Hackathon_VX_Desafio01_Cadastro_e_Saneamento.pdf`
com o que existe no projeto (branch `final`), onde está, se foi medido e com
qual número. Todo número tem fonte: um arquivo lido ou um comando rodado,
indicados na coluna "fonte" ou na nota abaixo da tabela.

## Fontes usadas

| Apelido | Caminho | O que é |
|---|---|---|
| **congelado** | `/tmp/claude-1000/-home-igor-alves-clas-hack-vxwinners/c958551b-a9b4-470d-acfc-2821b76b1588/scratchpad/artefatos_v2v3/` | saída da execução final (BERT + desempates do LLM + detecção de ausentes): `saneado_base.csv`, `decisoes_base.jsonl`, `plano_juncao.csv`, `catalogo_final.xlsx`, `completacoes_sugeridas.jsonl`, `deteccao_ausentes.jsonl` |
| **gabarito** | `congelado/avaliacao_gold_campos_cadastro.md` | `evaluate.py` contra `avaliacao/gold.csv` (456 rótulos, 177 itens), seção `pipeline_bert_llm.csv` |
| **v3** | `/tmp/claude-1000/-home-igor-alves-clas-hack-vxwinners/c958551b-a9b4-470d-acfc-2821b76b1588/scratchpad/v3/` | o que esta frente rodou, sem LLM e sem gravar nada no repositório (ver abaixo) |

O que foi rodado nesta frente (nada chama API paga, nada grava em `artefatos/`):

| Comando | Saída | Para quê |
|---|---|---|
| `scripts/06_juntar.py --artefatos v3/art_jun` sobre o `saneado_base.csv` congelado | `v3/art_jun/plano_juncao.csv` | os números da junção (capital, centros, risco de parada). O plano saiu **idêntico** ao congelado: 4.684 linhas com o mesmo par (código, ação, usar). A versão atual do script só acrescenta duas colunas |
| `scripts/09_enriquecer.py --artefatos v3/art_enr` sobre o `saneado_base.csv` congelado | `v3/art_enr/enriquecimento.csv`, `v3/enr_base.log` | se o enriquecimento roda e o que produz. Usa a tabela NCM já baixada em `dados/referencia/ncm_siscomex.json` (não baixa nada) |
| `scripts/04_extrair.py --pedidos --sem-llm --congelar-aprendizado --artefatos v3/art_ped` (BERT ligado, com `modelo_bert` por link simbólico) | `v3/art_ped/saneado_pedidos.csv` | os 520 pedidos de cadastro |
| `v3/pedidos.py`, `v3/casos*.py`, `v3/numeros.py` (scripts temporários) | só no terminal | cruzar pedidos × base, achar os casos equivalentes, recontar os números do congelado |

Os números de referência do pipeline foram recontados no congelado e batem:
23.554 registros; SANEADO 20.055 (85,1%), dos quais 15.536 completos (66,0%);
PENDENTE 3.362 (14,3%); REVISAO_HUMANA 100 (0,4%); FORA_DO_PDM 37; chaves
fechadas 16.996; 2.687 `BLOQUEADO` e 1.997 `MANTER ATIVO` no plano de junção;
capital em código redundante R$ 30.284.672,48 de R$ 200.874.691,83 (15,1%).

---

## 1. Resumo

| Frente | Exigências | Feito | Parcial | Falta |
|---|---|---|---|---|
| Problema (os quatro custos) | 4 | 3 | 1 | 0 |
| Saneamento | 9 | 3 | 5 | 1 |
| Cadastro | 3 | 0 | 1 | 2 |
| Enriquecimento | 3 | 1 | 2 | 0 |
| Dados fornecidos | 5 | 3 | 2 | 0 |
| Exemplos do briefing (caso equivalente) | 5 | 4 | 1 | 0 |
| Entregáveis | 3 | 0 | 2 | 1 |
| **Total** | **32** | **14** | **14** | **4** |

Perguntas para começar: 7. Três têm resposta com número, três têm resposta
parcial, uma não tem resposta medida (seção 9).

Há trabalho que existe **fora da branch `final`** e responde a exigências
marcadas aqui como "falta" ou "parcial": em `origin/modo-cadastro`, um backend
FastAPI com fluxo de estados do cadastro e uma tela de cadastro; em
`origin/main`, a `plataforma.html`; em `origin/analise-de-mercado`, o
`docs/03-analise-mercado.md`. Nada disso foi executado nesta frente. Os
números citados desses ramos vêm dos próprios documentos deles (seção 8).

---

## 2. O problema: os quatro custos do briefing

O briefing nomeia quatro custos (pág. 3). O projeto mede três deles em reais
ou em contagem.

| Exigência (citada) | Onde está | Medido? | Número e fonte | Status | Ação para fechar |
|---|---|---|---|---|---|
| "CAPITAL PARADO · O mesmo item estocado várias vezes, com códigos diferentes." | `06_juntar.py` → `plano_juncao.csv` | sim (sem IC) | R$ 30.284.672,48, 15,1% do estoque de R$ 200,9 mi (`06_juntar.py` sobre o congelado) | feito | dar faixa com a precisão da junção (V4) |
| "COMPRA FRAGMENTADA · Itens iguais comprados separados, sem escala para negociar." | `06_juntar.py` | sim | 1.659 clusters em 2 ou mais centros; R$ 49.623.349,91 negociáveis em conjunto; dispersão de preço do mesmo item R$ 6.990.464,89 (`06_juntar.py`) | feito | — |
| "OPERAÇÃO PARADA · Manutenção esperando uma peça que já estava no almoxarifado." | `06_juntar.py` | sim (contagem) | 1.132 clusters com risco de parada: um código com saldo, outro zerado (`06_juntar.py`) | feito | — |
| "RISCO FISCAL · NCM errado que vira problema com o fisco." | `NCM_PDM`, `NCM_MOTIVO` em `saneado_base.csv`; `09_enriquecer.py` | parcial | 1.104 NCM divergentes da classe corrigidos; 515 fora da lista condicional da classe; 15 NCM `7306.30.00` não vigentes na tabela oficial (`v3/enr_base.log`). Sem valor em reais no `final` | parcial | calcular a base fiscal exposta (o ramo `analise-de-mercado` tem R$ 9,47 mi, por outro método) |

---

## 3. Saneamento: corrigir a base que já existe

| Exigência (citada) | Onde está | Medido? | Número e fonte | Status | Ação para fechar |
|---|---|---|---|---|---|
| "Juntar duplicidades" | `scripts/06_juntar.py`: mesma chave de identidade (classe + obrigatórios, ou fabricante + part number) → `plano_juncao.csv` | parcial | 2.687 códigos redundantes em 1.997 clusters; 16.996 chaves fechadas (congelado). **Precisão da junção não medida**: `avaliacao/pares_juncao_cego.csv` tem 150 pares sem rótulo | parcial | rotular os 150 pares e medir a precisão (prompt de características) |
| "um dos três códigos continua ativo [...] Os outros dois são bloqueados e passam a apontar para ele" | `plano_juncao.csv` (`ACAO` = `MANTER ATIVO` / `BLOQUEADO`, `USAR`); aba `JUNCOES` e colunas `ACAO`, `USAR_CODIGO` da aba `CATALOGO` | sim (contagem) | 1.997 `MANTER ATIVO`, 2.687 `BLOQUEADO` com `USAR`; sobrevivente por regra explícita (ativo, completude, movimentação, valor, código mais antigo). Escolha do sobrevivente não avaliada (V2.3) | feito | medir o sobrevivente (V2.3) |
| "o estoque dos três vira um só" | `plano_juncao.csv`, coluna `ESTOQUE_CONSOLIDADO` | conferido em 2 clusters | 4 + 1 + 3 + 0 = 8 no cluster 29853004; 26 + 4 = 30 no cluster 18440210 (seção 7.1) | feito | — |
| "padronizar descrições" | `DESCRICAO_PDM` em `saneado_base.csv` e na aba `CATALOGO` | parcial | no formato PDM: 4.877 (20,7%) antes, 23.517 (99,8%) depois (aba `RESUMO` do catálogo). Mede o **formato**, não se o conteúdo está certo | parcial | gabarito da descrição (V2.2) |
| "acertar unidade" | `UNIDADE_PDM`, `UNIDADE_MOTIVO` (`validador.py`) | parcial | 1.516 unidades trocadas pela da classe; 978 ficam vazias porque CT, JG, CX, BR, RL, GL, BD são embalagem e falta o fator de conversão; dentro do padrão da classe: 21.085 antes, 22.539 depois (aba `RESUMO`). Precisão não medida | parcial | gabarito de unidade (V2.1); fila de fator de conversão para as 978 |
| "acertar [...] NCM" | `NCM_PDM`, `NCM_MOTIVO` | sim | gabarito: precisão 96,6% [88–99%], cobertura 89%, 56 acertos e 2 erros em 65; NCM no formato `0000.00.00`: 13.901 antes, 22.943 depois (aba `RESUMO`); 597 derivados da classe quando ausentes | feito | — |
| "acertar [...] grupo" | `GRUPO_CORRIGIDO` (0/1) em `saneado_base.csv`; o grupo certo é o da classe (`ID_PDM`) | sim, mas fora do repositório | gabarito: 98,5% [95–100%], 135 de 137. **O valor corrigido não é gravado**: 616 registros têm `GRUPO_CORRIGIDO = 1`, mas a coluna `GRUPO_MERCADORIA` do catálogo é a original em 23.554 de 23.554. O CSV avaliado (`scratchpad/eval/pipeline_bert_llm.csv`) foi montado fora do repositório | parcial | gravar o grupo da classe no `saneado_base.csv` e no catálogo; versionar o script que monta o CSV de avaliação (`scripts/16_avaliar_campos_cadastro.py` está sendo criado, não versionado) |
| "A classe de pressão e o material exato [...] vieram do catálogo do fabricante (enriquecimento, por exemplo com IA)" | `scripts/09_enriquecer.py` (fontes normativas); `scripts/14_sugerir_completacoes.py` (completação de dado genérico) | parcial | enriquecimento: 563 dados novos em 559 registros, mas só 212 das 10.946 caixas obrigatórias vazias (1,9%) (`v3/enr_base.log`). Completações: 3.266 linhas; faixa PROVÁVEL acerta 96,0% no teste retroativo (docs/12). **O enriquecimento não volta para `saneado_base.csv`, catálogo ou junção** | parcial | aplicar `enriquecimento.csv` no saneado e na chave, com a fonte na trilha |
| "ou de uma confirmação manual, feita no sistema pelo responsável pelo cadastro" | as perguntas existem (`completacoes_sugeridas.jsonl`, campo `pergunta`; aba `PENDENCIAS` com 10.946 linhas), mas não há onde responder | não | — | falta | no `final` não há tela. O ramo `modo-cadastro` tem revisão com papel de revisor (seção 8) |

Apoio, sem exigência própria no briefing: a detecção de ausentes separou
AUSENTE (6.602 caixas), PRESENTE_FORA_DO_PADRAO (3.464) e PERDIDO (437),
contadas em `congelado/deteccao_ausentes.jsonl`.

---

## 4. Cadastro: padronizar o que está chegando

**O fluxo de estados `APROVADO` / `JA_EXISTE` / `DEVOLVIDO` / `FORA_DO_PDM` não
existe na branch `final`.** `grep` por `JA_EXISTE`, `DEVOLVIDO` e `APROVADO` em
`src/` e `scripts/` não acha nada. O pipeline tem só os estados de registro
(`SANEADO`, `PENDENTE`, `REVISAO_HUMANA`, `FORA_DO_PDM`). `04_extrair.py --pedidos`
lê os 520 pedidos (juntando `TEXTO_SOLICITACAO` e `CONTEUDO_ANEXO`, em
`dados.ler_pedidos`) e extrai. Não compara com a base, não devolve e não grava
artefato em `artefatos/`.

Resultado da extração dos pedidos rodada nesta frente (`v3/art_ped/saneado_pedidos.csv`):
SANEADO 432, FORA_DO_PDM 62, REVISAO_HUMANA 25, PENDENTE 1; 353 completos;
376 com chave fechada. **Unidade vazia em 520 de 520**: o pedido não traz
unidade e o pipeline não aplica a `UNIDADE_PADRAO` da classe. NCM vazio em 303.
Os pedidos rodaram sem `--aplicar-deteccao`, então dado genérico pode estar
contado como SANEADO.

Simulação do fluxo (script temporário `v3/pedidos.py`, **não é recurso do
projeto**): `JA_EXISTE` se a chave do pedido existe na base congelada;
`APROVADO` se está SANEADO e completo; `FORA_DO_PDM` se não tem classe; senão
`DEVOLVIDO`. Resultado: APROVADO 252, DEVOLVIDO 121, **JA_EXISTE 85**,
FORA_DO_PDM 62.

| Exigência (citada) | Onde está | Medido? | Número e fonte | Status | Ação para fechar |
|---|---|---|---|---|---|
| "Transformar um pedido de item novo, que chega em texto livre, ficha técnica ou catálogo, num cadastro no padrão" | `04_extrair.py --pedidos`; `dados.ler_pedidos` junta o anexo (107 fichas técnicas e 29 catálogos de fornecedor no `02_pedidos_cadastro.xlsx`) | parcial | 353 de 520 completos; 376 com chave (`v3/art_ped`). Sem gabarito; unidade nunca preenchida | parcial | preencher unidade e NCM pela classe; gravar `saneado_pedidos.csv` na cadeia (`rodar_completo.sh`) |
| "Antes de criar, conferir se o item já existe na base" | não existe no `final` | só na simulação desta frente | 85 de 520 pedidos (16,3%) têm a mesma chave de um item da base (`v3/pedidos.py`) | falta | script que cruza a chave do pedido com a base e grava `JA_EXISTE` + o código existente |
| "e devolver o pedido quando falta informação" | `PENDENTES` diz o que falta; não há estado nem mensagem | não | 121 seriam devolvidos pela simulação | falta | estado `DEVOLVIDO` com a lista de pendências e a pergunta do `14_sugerir_completacoes.py` |

---

## 5. Enriquecimento: completar o que falta

`scripts/09_enriquecer.py` **roda** sem rede, com a tabela NCM já baixada
(10.516 códigos, "Vigente em 07/11/2026", baixada em 2026-11-07, Resolução
Gecex nº 926/2026). Em 23.554 registros, deu 563 dados novos com procedência:
182 `iso15_rolamento`, 123 `din_iso_porca`, 89 `din_iso_parafuso`, 89
`iso4184_correia`, 53 `designacao_fabricante`, 16 `prefixo_part_number_filtro`
e 11 `din_broca`. Preservou 6.683 caixas já ocupadas e teve 0 recusas pelo
validador do PDM. Na conferência de NCM: 22.928 vigentes, 15 não vigentes, 574
ausentes e 68 preenchidos (`v3/enr_base.log`). O `enriquecimento.csv` tem 646
linhas, todas com `FONTE` e `URL_OU_REFERENCIA`; 32 marcadas `REVISAR=1`.

| Exigência (citada) | Onde está | Medido? | Número e fonte | Status | Ação para fechar |
|---|---|---|---|---|---|
| "Buscar em fontes externas, como catálogos de fabricantes e normas técnicas, a informação que o cadastro não tem" | `src/saneamento/enriquecimento.py`: (a) tabela oficial NCM; (b) tabelas normativas no código (ISO 15, ISO 261, ISO 4014/4017/4032, ISO 4184, sistemas de designação); (c) catálogo de fabricante | parcial | (a) e (b) funcionam: 563 dados. (c) **foi tentado e não funcionou**: SKF e Schaeffler respondem uma página de JavaScript sem as dimensões no HTML (`CATALOGO_TENTADO`, `v3/enr_base.log`) | parcial | aceitar (b) como a fonte e dizer isso no pitch; ou buscar PDF de catálogo |
| "e conferir antes de gravar" | invariantes do `Enriquecedor`: valor fora da lista do PDM é recusado, nunca sobrescreve a extração, dado sem procedência não entra | sim | 0 recusados pelo validador; 6.683 caixas preservadas; 0 recusados sem procedência; nos 15 produtos reais, 32 dados e 0 erros (docs/09, seção 8; o `v3` reproduz os 32 dados) | parcial | os dados conferidos **não são gravados**: falta aplicá-los ao saneado e ao catálogo (seção 3) |
| "Cada dado novo precisa dizer de onde veio" | colunas `FONTE`, `URL_OU_REFERENCIA`, `DATA_CONSULTA`, `CONFIANCA`, `DERIVADO_DE`, `METODO` do `enriquecimento.csv`; para a extração, `fonte` e `evidencia` por caixa em `decisoes_base.jsonl` | sim | 646 de 646 linhas com fonte e referência (`v3/art_enr/enriquecimento.csv`); aba `RESUMO`: origem de cada valor (acordo 56,1%, rótulo 14,5%, gazetteer 7,9%, LLM 1,5%...) | feito | — |

---

## 6. Dados fornecidos

| Exigência (citada) | Onde está | Medido? | Número e fonte | Status | Ação para fechar |
|---|---|---|---|---|---|
| "Uma base de materiais [...] com os problemas típicos de uma base real" | `dados.ler_base`; todo o pipeline | sim | 23.554 registros processados; STATUS na origem: 20.014 ATIVO, 2.331 BLOQUEADO, 1.209 OBSOLETO (`01_base_materiais.xlsx`) | feito | — |
| "Um conjunto de pedidos de cadastro de itens novos, em formatos variados" | `dados.ler_pedidos`, `04_extrair.py --pedidos` | parcial | 520 pedidos: canal PORTAL 279, EMAIL 156, PLANILHA 85; 136 com anexo (`02_pedidos_cadastro.xlsx`). Extraídos nesta frente, sem artefato na cadeia | parcial | ver seção 4 |
| "Material de referência sobre o padrão descritivo de materiais (PDM)" | `01_compilar_pdm.py` → `pdm.json`; regras 2, 10, 12 e 13 do PDM aplicadas no código | sim | 44 classes, 229 atributos (`03_padrao_cadastro_PDM.xlsx`, aba `ATRIBUTOS`) | feito | — |
| "Os últimos 15 registros da base de materiais são produtos reais." | estrato `plantados` do `avaliacao/gold.csv` | parcial | gabarito, estrato `plantados`: grupo 100% [80–100], NCM 100% [68–100], fabricante 100% [77–100], referência 88,9% [56–98]. Junção: 11315577 e 29458054 (CAT 1R1808) unidos, certo; 6205 SKF / FAG / NSK não unidos, certo pela regra 13. **Duplicidade perdida**: 27841570 `FILTRO LF9009` e 16031971 `FILTRO OLEO LUBRIFICANTE FLEETGUARD LF 9009` não se juntam, porque a referência do segundo foi lida como `9009` e o fabricante do primeiro ficou pendente. 6 rolamentos estão PENDENTE só por `VEDACAO`, que o enriquecimento preenche (2RSH, 2HRS, DDU → borracha; 2Z, ZZ → metálica) | parcial | corrigir a leitura de `LF 9009`; aplicar o enriquecimento (os 15 fechariam as 8 obrigatórias que faltam) |
| "Fontes públicas [...] podem ser usadas à vontade, desde que a fonte de cada dado seja registrada." | `dados/referencia/ncm_siscomex.json` com metadados; procedência no `enriquecimento.csv` | sim | tabela oficial com vigência e ato registrados; 646 de 646 dados com fonte | feito | — |

---

## 7. Os exemplos do briefing e seus casos equivalentes reais

Os códigos do briefing (`10293847`, `20384756`, `10482213`, `17730415`,
`24019866`) não estão na base: são ilustrativos. Para cada um, abaixo está um
caso real da base com o antes (`01_base_materiais.xlsx`) e o depois
(`congelado/saneado_base.csv`, `plano_juncao.csv`, aba `CATALOGO`).

### 7.1 Duplicidade: "o mesmo item com três códigos" → feito

**Caso A, o mais parecido com o briefing: válvula borboleta DN 50 = 2", com quatro códigos.**

| Código | Antes: texto cru (descrição longa) | UN | NCM | Grupo | Status / estoque | Depois: ação |
|---|---|---|---|---|---|---|
| 29853004 | `VALVULA BORBOLETA DN 50 WAFER FOFO NODULAR FERRO FUNDIDO NODULAR NIQUELADO BORRACHA NITRILICA REDUTOR MANUAL` | PC | 84818097 | VAL01 | ATIVO / 4 | **MANTER ATIVO**, estoque consolidado 8 |
| 19556203 | `VALVULA BORBOLETA;BITOLA:2";TIPO CORPO:WAFER;CORPO:FERRO NODULAR;...;VEDACAO SEDE:NITRILICA;ACIONAMENTO:REDUTOR MANUAL` | PC | 8481.80.97 | **FIX01** | ATIVO / 1 | BLOQUEADO · USAR 29853004 |
| 29380832 | `NAO UTILIZAR - USAR COD 13827342 - VALVULA BORB; DIAMETRO NOMINAL:2 IN; TIPO CORPO:WAFER; ...` | PC | **84818099** | VAL01 | BLOQUEADO / 3 | BLOQUEADO · USAR 29853004 |
| 13827342 | `VALVULA BORBOLETA, DIAMETRO NOMINAL:DN 50, ..., VEDACAO SEDE:BUNA-N, ACIONAMENTO:REDUTOR MANUAL` | **UN** | 8481.80.97 | VAL01 | ATIVO / 0 | BLOQUEADO · USAR 29853004 |

Depois, os quatro: `ESTADO = SANEADO`, `PENDENTES` vazio, `UNIDADE_PDM = PC`,
`NCM_PDM = 8481.80.97`, `DESCRICAO_PDM` =
`VALVULA BORBOLETA; DIAMETRO NOMINAL: 2POL; TIPO CORPO: WAFER; MATERIAL CORPO: FERRO FUNDIDO NODULAR; MATERIAL DISCO: FERRO FUNDIDO NODULAR NIQUELADO; VEDACAO SEDE: NBR; ACIONAMENTO: REDUTOR`.
É o que o briefing descreve: `DN 50 = 2" = 2 IN`, `NITRILICA = BUNA-N = NBR`,
`VALV BORB = VALVULA BORBOLETA`, numa só chave. De quebra, a unidade `UN` e o
NCM `8481.80.99` foram corrigidos. Os 4 códigos estão em 3 centros (1300, 2100 e 1200).

Duas ressalvas para a banca. (1) A base já dizia "USAR COD 13827342" no texto
de 29380832, e o pipeline escolheu outro sobrevivente (29853004, com mais
estoque). A regra é explícita, mas contraria a indicação legada. (2) O grupo
`FIX01` de 19556203 continua na coluna `GRUPO_MERCADORIA` do catálogo (seção 3).

**Caso B, válvula de esfera (a mesma classe do briefing): `VALV ESF DN 100` = `4POL`.**

| Código | Antes | UN | NCM | Centro / status / estoque / preço | Depois |
|---|---|---|---|---|---|
| 18440210 | `VALV. ESFERA, BITOLA:4POL, CLASSE:150#, MATERIAL:ACO INOX FUNDIDO A351 CF8M, LIGACAO:FLANGEADA RF, PASSAGEM:STD, VEDACAO SEDE:TEFLON, ACIONAMENTO:PNEUMATICO` | PC | **84818096** | 1300 / ATIVO / 26 / R$ 222,12 | MANTER ATIVO, estoque consolidado 30 |
| 22937359 | `VALV ESF DN 100 150# ACO INOX FUNDIDO A351 CF8M FLANGE RF PLENA PTFE PNEUMATICO` | PC | 8481.8095 | 1100 / BLOQUEADO / 4 / R$ 621,21 | BLOQUEADO · USAR 18440210 |

Depois, os dois: SANEADO, completos, `NCM_PDM = 8481.80.95`, `DESCRICAO_PDM` =
`VALVULA ESFERA; DIAMETRO NOMINAL: 4POL; CLASSE PRESSAO: 150#; MATERIAL CORPO: ACO INOX FUNDIDO A351 CF8M; CONEXAO: FLANGE RF; PASSAGEM: PLENA; VEDACAO SEDE: PTFE; ACIONAMENTO: ATUADOR PNEUMATICO`.
`TEFLON = PTFE`, `STD = PLENA`. O mesmo item custa R$ 222 numa planta e R$ 621 em outra.

Outro cluster de três, com três redações diferentes: válvula de retenção
1.1/2" 300# CF8M BW (28678948 ativo; 10293003 e 22784778 bloqueados, com
`1,5POL`, `1 1/2 POL` e `1.1/2"`).

### 7.2 Informação faltando: "parafuso sem classe de resistência" → parcial

**Caso real: 13335564 `PARAF. SEXTAVADO MA M8X80 ACO CARB ZINC DIN 933`**
(base: UN `PC`, NCM `7318.1500`, grupo `SOL01`, estoque 116). É o caso do
briefing: tipo, medida e acabamento, sem classe de resistência.

Depois: `ESTADO = PENDENTE`, `PENDENTES = ACABAMENTO | CLASSE RESISTENCIA`,
`NCM_PDM = 7318.15.00`, `UNIDADE_PDM = PC`, sem chave de identidade (não entra
em junção), e `DESCRICAO_PDM` =
`PARAFUSO SEXTAVADO; ROSCA: METRICA GROSSA; BITOLA: M8; COMPRIMENTO: 80MM; CLASSE RESISTENCIA: <PENDENTE>; MATERIAL: ACO CARBONO; ACABAMENTO: <PENDENTE>; NORMA: DIN 933`.
A detecção marcou a classe como `AUSENTE` e `ZINC` como genérico. O projeto
gera a pergunta: *"O cadastro diz 'ZINC' para ACABAMENTO. Qual destes: ZINCADO
BRANCO (61%); ZINCADO AMARELO (39%)?"* (`completacoes_sugeridas.jsonl`).

Variante: 11578236 `PARAFUSO SEXT. METRICA GROSSA M-24X80 CARBONO ZINCADO BRANCO DIN 933`
fica `SANEADO`, incompleto, com `PENDENTES = CLASSE RESISTENCIA`, também sem chave.

Por que parcial: para a classe de resistência **ausente** não há pergunta nem
sugestão, só a pendência na aba `PENDENCIAS` ("dicionario/LLM, ou
enriquecimento se nao estiver no texto"). E a contagem de parafusos sem classe
está misturada com erro de classificação. São 398 registros `PDM001` com
`CLASSE RESISTENCIA` pendente, mas em só 154 o texto não traz nenhuma classe
(conta por padrão de texto, `v3/casos3.py`). No `PDM001` há 214 textos de
parafuso Allen ou sextavado interno (deveriam ser `PDM002`) e 54 de arruela.
O `docs/06-plano-modo-cadastro.md` do ramo `modo-cadastro` aponta a mesma
divergência: 281 parafusos Allen.

### 7.3 Classificação errada: "a porca com NCM de parafuso" → feito

**Caso real, praticamente o do briefing: 29021750 `PORCA SEXTAVADA METRICA GROSSA M10 8 DIN 934`, NCM `7318.15.00`** (o NCM de parafuso, PDM001), UN `PC`.

Depois: `NCM_PDM = 7318.16.00`, `NCM_MOTIVO = divergente: classe PDM003 exige 7318.16.00`,
`ESTADO = SANEADO` (incompleto), `PENDENTES = ACABAMENTO | MATERIAL`,
`DESCRICAO_PDM` = `PORCA; TIPO: SEXTAVADA; ROSCA: METRICA GROSSA; BITOLA: M10; CLASSE RESISTENCIA: 8; MATERIAL: <PENDENTE>; ACABAMENTO: <PENDENTE>; NORMA: DIN 934`.
O enriquecimento é que propõe a norma (`din_iso_porca`).

Na base há 21 porcas com NCM de parafuso (7318.15), e o pipeline corrigiu as
21. Há 39 porcas com NCM divergente da classe e 1.104 registros no total.
Outro caso com acabamento zincado: 25701439 `PORCA, TIPO:SEXTAVADA, ..., BITOLA:M-24, CLASSE:8, ACABAMENTO:ZINC AMARELO, ...`,
NCM `73181500` → `7318.16.00`. A unidade era `JG` e ficou vazia, por falta do
fator de conversão.

No gabarito, o caso equivalente medido é 25560040 (arruela de pressão com NCM
de arruela lisa): o NCM da base `7318.22.00` está errado e o pipeline acerta
`7318.21.00`. O caso some da lista de erros entre `base_original.csv` e
`pipeline_bert_llm.csv`.

### 7.4 Cadastro: "preciso de 10 parafuso sextavado m16 x 60 galvanizado 8.8 din 933" → feito

**Pedido real SC-202600156** ("Peço por favor cadastrar parafuso sextavado [...] Rosca: metrica grossa - Bitola: M16 - Comprimen[to] ...") →
`SANEADO`, completo:
`PARAFUSO SEXTAVADO; ROSCA: METRICA GROSSA; BITOLA: M16; COMPRIMENTO: 65MM; CLASSE RESISTENCIA: 8.8; MATERIAL: ACO CARBONO; ACABAMENTO: ZINCADO AMARELO; NORMA: DIN 933`,
NCM `7318.15.00`, com chave fechada. Contraexemplo que deveria ser devolvido:
SC-202600011 ("parafuso sextavado metrica fina 180 mm 8.8 [...] din 933"), que
fica SANEADO mas com `PENDENTES = BITOLA`. Nos dois a unidade sai vazia (seção 4).

### 7.5 Enriquecimento: "ROL 6206-2RSH SKF" → feito (fora da cadeia)

**Caso real: 20866024 `ROL 6205-2RSH/C3 SKF`** (um dos 15 produtos reais).
Extração: `ROLAMENTO RIGIDO ESFERAS; REFERENCIA: 6205-2RSH/C3; VEDACAO: <PENDENTE>; FOLGA: C3`, `PENDENTE`.
Enriquecimento (`v3/art_enr/enriquecimento.csv`): `DIAMETRO INTERNO 25MM`, `DIAMETRO
EXTERNO 52MM`, `LARGURA 15MM`, fonte `iso15_rolamento` ("ISO 15:2017 [...] série 02",
confiança 0,97), e `VEDACAO BORRACHA AMBOS LADOS`, fonte `designacao_fabricante`
("ISO 5753-1 / sistemas de designação SKF, FAG, NSK, ...", sufixo 2RSH). A fonte é
a norma, não o catálogo SKF, que não foi acessível. O dado não volta ao catálogo.

---

## 8. Entregáveis

| Exigência (citada) | Onde está | Medido? | Número e fonte | Status | Ação para fechar |
|---|---|---|---|---|---|
| "Um MVP funcional, demonstrado na prática." | `final`: pipeline de linha de comando + `catalogo_final.xlsx` (50 abas: `RESUMO`, `CATALOGO`, 44 de classe, `ANTES_DEPOIS`, `CARACTERISTICAS`, `PENDENCIAS`, `JUNCOES`). **Sem interface no `final`.** Fora dele: `plataforma.html` em `origin/main`; backend FastAPI + PostgreSQL + `frontend/cadastro.js` + teste e2e em `origin/modo-cadastro`, com estados `RASCUNHO`, `AGUARDANDO_SOLICITANTE`, `EM_REVISAO`, `APROVADO`, `JA_EXISTE`, `FORA_DO_PDM` (`backend/app/cadastro/modelo.py`) | não (ramos não executados aqui) | segundo o `docs/06-plano-modo-cadastro.md` daquele ramo: 99,5% da base com classe, 78,2% com chave, 276 testes. Não conferido | parcial | escolher **uma** demo e ligá-la aos artefatos do `final` (o backend do ramo tem `comparar-pipelines` contra `saneado_base.csv`) |
| "Uma análise de mercado e do problema." | `final`: `scripts/analise_mercado.py` quantifica o **problema** a partir da base, sem mercado. Fora dele: `docs/03-analise-mercado.md` em `origin/analise-de-mercado` e `origin/modo-cadastro` | parcial | aquele documento diz R$ 36,6 mi de "ganho direto endereçável" e R$ 3,94 mi de capital parado (piso, por casamento de texto). O pipeline mede R$ 30,3 mi. **Números diferentes para a mesma coisa** | parcial | trazer o documento ao `final` e reconciliar com os números do pipeline |
| "Cinco minutos para a banca." | — | não | — | falta | roteiro com os números do manifesto (V1) e os casos da seção 7 |

---

## 9. Perguntas para começar

| Pergunta do briefing | Resposta que o projeto dá | O que sustenta |
|---|---|---|
| "Quem convive com esse problema no dia a dia, e do que essa pessoa precisa para confiar no resultado?" | O responsável pelo cadastro, suprimentos e manutenção. Para confiar, cada valor tem fonte e trecho do texto, e cada junção se explica numa frase ("todos os obrigatórios coincidem"). **Parcial**: não houve conversa com usuário | `decisoes_base.jsonl` (fonte, evidência e motivo por caixa); aba `ANTES_DEPOIS` (129.525 linhas); invenção 0 de 109 no gabarito |
| "O que faz dois registros serem o mesmo item? E quando parecem iguais, mas não são?" | Mesma classe e os mesmos valores em todos os obrigatórios, inclusive os condicionais; nas classes de referência, o mesmo fabricante e o mesmo part number. Parecem iguais e não são: equivalentes de marcas diferentes (regra 13), cabos que só diferem pela cor, condicional ignorado. **Parcial**: a precisão da junção não foi medida | 2.687 redundantes (`plano_juncao.csv`); 534 junções falsas evitadas ao incluir os condicionais (docs/00, seção 5); 6205 SKF/FAG/NSK não unidos (seção 6); gabarito de junção sem rótulo (150 pares) |
| "O que custa mais caro: juntar dois itens diferentes ou deixar uma duplicidade passar?" | Posição de projeto: juntar errado é pior (bloqueia um código bom e manda comprar a peça errada), por isso a junção exige igualdade de chave e nunca similaridade. O custo de deixar passar existe e não está contado: por exemplo, o LF9009 da seção 6 | **sem resposta medida**. Falta a precisão da junção e o valor de um falso positivo (V4) |
| "Quando falta uma informação, onde buscar, e como saber se a fonte é confiável?" | Primeiro a tabela oficial (Siscomex), depois a norma técnica codificada (ISO 15, DIN/ISO), por último o catálogo do fabricante, que não foi acessível. A fonte é confiável quando é determinística e citável, quando o valor passa no validador do PDM e quando não contradiz o que foi extraído | 646 de 646 dados com fonte; 0 recusados; 6.683 caixas preservadas (`v3/enr_base.log`); 15 produtos reais: 32 dados, 0 erros (docs/09) |
| "Quando a decisão pode ser automática, e quando precisa de alguém validando?" | Automática: regra determinística ou acordo entre regra e BERT, valor na lista do PDM. O LLM só desempata e passa pelo mesmo validador. Sugestão nunca entra na caixa: vira pergunta, com confirmação simples na faixa PROVÁVEL (≥ 90%) e escolha aberta nas outras. Conflito vai para revisão humana | faixa PROVÁVEL acerta 96,0% em 6.891 casos; geral 81,9% (docs/12); REVISAO_HUMANA 100 (0,4%); auditoria do LLM 19 de 20 (docs/09) |
| "Vale mais corrigir o que já existe ou impedir que o erro entre?" | O projeto fez a correção. Impedir é o fluxo de cadastro, que não está no `final`. **Parcial**: há uma medida indireta do valor de impedir | 85 de 520 pedidos (16,3%) pedem item que já existe na base pela chave (`v3/pedidos.py`, simulação) |
| "Como provar que a base ficou melhor?" | Antes e depois, medidos na mesma base, mais um gabarito independente com intervalo de confiança e taxa de invenção | formato PDM 20,7% → 99,8%; NCM no formato 13.901 → 22.943; unidade no padrão 21.085 → 22.539 (aba `RESUMO`); gabarito 96,7% [94–98%] de precisão (318 de 329), cobertura 95% (329 de 347), invenção 0 de 109 (soma das linhas do `gabarito`). Faltam o determinismo (V1) e a precisão da junção |

---

## 10. O que falta, em ordem de impacto no pitch

1. **Precisão da junção.** Os 150 pares de `avaliacao/pares_juncao_cego.csv`
   ainda não têm rótulo. É o que sustenta os R$ 30,3 mi e os 2.687 códigos, o
   número principal do pitch, e é o que a banca vai perguntar primeiro. Sem
   ela, a pergunta "o que custa mais caro" fica sem número (V4).
2. **Fluxo de cadastro no `final`**: `JA_EXISTE` / `DEVOLVIDO` / `APROVADO` /
   `FORA_DO_PDM` sobre os 520 pedidos, gravando um artefato. A simulação já
   dá o slide (85 já existem, 121 devolvidos), mas precisa virar script da
   cadeia, preencher unidade e NCM pela classe e aplicar a detecção de genérico.
3. **Uma demo só.** No `final` não há interface; em `origin/modo-cadastro` há
   backend com estados e tela; em `origin/main`, a `plataforma.html`. Escolher
   uma, ligá-la aos artefatos do `final` e ensaiar com os casos da seção 7.
4. **Pitch de 5 minutos**, com os números vindos do manifesto e os três
   exemplos do briefing trocados pelos casos reais (válvula 29853004 com 4
   códigos, parafuso 13335564, porca 29021750).
5. **Integrar o enriquecimento** ao saneado, ao catálogo e à chave: hoje ele
   roda, mas fica num arquivo à parte. Fecha a `VEDACAO` dos 6 rolamentos e o
   fabricante de 2 filtros reais. Junto, corrigir a leitura de `LF 9009`, uma
   duplicidade real perdida entre os 15 produtos reais.
6. **Reconciliar a análise de mercado** do ramo `analise-de-mercado`
   (R$ 36,6 mi e R$ 3,94 mi) com os números do pipeline (R$ 30,3 mi) e
   trazê-la ao `final`.
7. **Gravar o grupo corrigido** (616 registros) no saneado e no catálogo, e
   versionar o script que monta o CSV avaliado. Hoje o 98,5% de grupo sai de
   um CSV montado fora do repositório.
8. **Gabaritos de unidade, descrição e sobrevivente** (V2), e corrigir a classe
   dos parafusos Allen e das arruelas que estão em `PDM001` (214 e 54 pela
   conta por texto).
