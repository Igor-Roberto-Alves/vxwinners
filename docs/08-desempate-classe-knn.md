# Desempate de classe por kNN de embedding

Data: 2026-11-07. Só medição: **o pipeline não foi alterado**. Script:
`scripts/13_medir_desempate_classe.py`.

## 1. A pergunta

O classificador léxico (`regras._buscar`) pontua cada classe por *letras do
substantivo + letras do qualificador*. Quando o texto não traz o qualificador,
as classes irmãs empatam (as 5 válvulas fazem 7 pontos cada) e o código fica
com **a primeira da lista**. Foi assim que as válvulas de retenção viraram
válvula esfera (ver `docs/07-abreviacoes.md`).

A ideia testada: usar similaridade de cosseno para escolher a classe.

## 2. Cosseno contra o nome da classe: não funciona

Cada classe vira o vetor do seu nome (`VALVULA RETENCAO`), e o registro vai
para a mais próxima.

- Nos 645 registros em que o léxico tem confiança 0,95 (substantivo e
  qualificador casados), o cosseno concorda em só **90,7%**.
- Os erros são grosseiros: `FILTRO HIDRAULICO HYDAC` → MANGUEIRA HIDRAULICA;
  `FILTRO OLEO LUBR` → OLEO LUBRIFICANTE; `ANEL ORING DIAM INTERNO` →
  PARAFUSO SEXTAVADO INTERNO.
- A diferença entre o 1º e o 2º colocado tem mediana de **0,012**, e 73% dos
  registros ficam abaixo de 0,02.

O embedding faz uma média da frase, e a palavra comum aos dois lados
(`HIDRAULICA`, `OLEO`, `INTERNO`) pesa mais que o substantivo. É o mesmo
fenômeno da seção 6 de `00-estado-do-projeto.md`.

## 3. kNN contra registros já classificados

O registro vai para a classe dos 7 registros mais parecidos entre os que o
léxico classifica com segurança, com voto ponderado pela similaridade. Um filtro
hidráulico fica perto de outros filtros hidráulicos, não de mangueiras.

### População em que o kNN poderia atuar (23.554 registros)

| Situação do léxico | Registros |
|---|---|
| substantivo só (conf 0,80) | 11.320 |
| seguro (substantivo + qualificador) | 9.840 |
| **empate entre classes irmãs** | **1.123** |
| **grupo corrigido** (busca nas 44 classes) | **589** |
| demais (conf 0,50–0,85) | 645 |
| sem classe | 37 |

### Resultado por situação

| Situação | Trocas propostas (voto ≥ 0,85) | Revisão a mão | Veredito |
|---|---|---|---|
| **empate** | 247 de 1.123 | **243 certas, 4 erradas** (~98%) | **usar** |
| grupo corrigido | 161 de 589 | o kNN erra a grande maioria; o léxico estava certo | **não usar** |
| como auditor dos "seguros" | 5.734 alarmes | quase todos falsos (3.202 só de sobressalente PDM110 → filtro) | **não usar** |

**Por que funciona no empate e falha no resto:** no empate, as candidatas
compartilham o substantivo e o kNN só precisa distinguir o qualificador entre
irmãs (gaveta ou esfera, autocompensador ou rígido). Na escolha aberta,
dominam as palavras de contexto: um pino, uma bucha e um filtro "de
escavadeira hidráulica Caterpillar" ficam todos parecidos.

### As trocas no empate

| Léxico (primeira da lista) | kNN | Trocas | Por que o léxico empatou |
|---|---|---|---|
| parafuso sextavado | parafuso sextavado **interno** | 152 | `CAB SEXTAVADA INTERNO`, `HEXAGONAL INTERNO`, `ALLEN`: o qualificador `SEXTAVADO INTERNO` não casa (gênero, sinônimo) |
| rolamento rígido esferas | rolamento **autocompensador** rolos | 48 | `AUTOCOMP`, `AUTO-COMPENSADOR`, `ROLETES` |
| rolamento rígido esferas | rolamento **rolos cônicos** | 12 | `ROL CONICO`, `ROLETES CONICOS` |
| válvula esfera | válvula **gaveta** | 19 | `GAV` |
| válvula esfera | válvula **borboleta** | 6 | `BORB` |
| arruela lisa | arruela **pressão** | 5 | `PRES`, `MOLA`, `DIN 127` |
| mangueira hidráulica | mangueira **industrial** | 2 | `SUCCAO` |
| conexão (PDM050) | luva **segurança** | 2 | `LUVA EPI` (certo) e `LUVA ... SOCKET WELD` (**errado**) |

As 152 trocas de parafuso trazem `INT`, `INTERNO` ou `ALLEN` no texto: todas
certas. As 4 erradas:

- `VALV GAV DIAMETRO 3/4 IN` → válvula **globo** (o certo é gaveta);
- `MANCAL PEDESTAL COM ROLAMENTO UCP204/UCP205` (2) → rolamento autocompensador.
  O certo é mancal, e o léxico também errava;
- `LUVA 1 1/2 POL 6000# SOCKET WELD` → luva de segurança. É conexão, e o léxico
  acertava.

O saldo é de 243 registros corrigidos, 2 que já estavam errados e continuam
errados, e **2 que estavam certos e ficariam errados**.

### Efeito no pipeline

A base foi reprocessada só com regras, **sem o dicionário aprendido**
(`Pipeline(pdm)` puro), com e sem as 247 trocas:

| Indicador | Sem kNN | Com kNN | Δ |
|---|---|---|---|
| SANEADO | 8.746 | 8.790 | **+44** |
| Chaves fechadas | 9.956 | 10.010 | **+54** |
| Códigos redundantes | 1.174 | 1.181 | **+7** |
| Registros que pioraram de estado | — | — | **0** |

As 7 junções novas foram conferidas a mão e **as 7 estão certas**. Exemplo que
vale para o pitch:

```
29618759  VALVULA GAVETA; DIAMETRO NOMINAL: 6POL; CLASSE PRESSAO: 150#;
          MATERIAL CORPO: ACO INOX FUNDIDO A351 CF8M; CONEXAO: FLANGE RF ...
16000573  VALVULA  GAV BITOLA DE DN150 150# MATERIAL DE CF8M FLANGE RF
          COM CASTELO APARAFUSADO REDUTOR MANUAL
```

Mesmo item: `GAV` = gaveta, `DN150` = `6POL`, `CF8M` = `A351 CF8M`. O léxico
punha o segundo em válvula esfera.

## 4. Recomendação

1. **Primeiro as regras.** Quase todo empate vem de um vocabulário que falta, e
   cada lacuna é uma linha de dicionário determinística e auditável: `GAV` →
   GAVETA, `BORB` → BORBOLETA, `PRES` → PRESSAO, `AUTOCOMP`/`AUTO-COMPENSADOR`
   → AUTOCOMPENSADOR, `ROLETES` → ROLOS, `SEXTAVADA INTERNO`/`HEXAGONAL
   INTERNO`/`ALLEN` → SEXTAVADO INTERNO, `ARRUELA MOLA` → ARRUELA PRESSAO. O kNN
   serviu para **descobrir** essas lacunas.
2. **kNN como desempate do que sobrar**, só entre as classes empatadas e só com
   voto ≥ 0,85. A fonte do sujeito fica registrada como `knn` na trilha de
   auditoria.
3. **Nunca kNN em escolha aberta** (grupo corrigido, auditoria geral): ali ele
   erra com voto alto.

Os números de concordância das seções 2 e 3 comparam o kNN com o léxico, e não
com uma verdade. A taxa de acerto da seção 3 vem de uma leitura do texto de
cada uma das 247 trocas, feita pelo Claude nesta sessão. Ela ainda não foi
conferida por uma pessoa do time e não substitui o conjunto-ouro.
