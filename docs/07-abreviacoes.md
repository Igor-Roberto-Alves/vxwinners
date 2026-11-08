# Abreviações ambíguas

Data: 2026-11-07. Arquivos alterados: `src/saneamento/texto.py`,
`tests/test_texto.py`. Script novo: `scripts/12_comparar_execucoes.py`.

## 1. Como a abreviação é tratada

São três mecanismos, em ordem de risco:

| Mecanismo | Onde | Escopo | Risco |
|---|---|---|---|
| Tabela de abreviações | `texto.py`, `ABREVIACOES` + `expandir()` | **todo o texto**, qualquer classe, antes de qualquer casamento | alto: não conhece a classe nem o atributo |
| Sinônimos de domínio | `sinonimos.py` | o texto de **uma caixa**, só aceito se o valor está na lista do atributo | baixo |
| Dicionário aprendido | `aprendizado.json` | por atributo, também travado pela lista | baixo, mas com risco de auto-reforço |

O texto expandido por `expandir()` alimenta a classificação do sujeito
(`regras._buscar`, que **não** tem fallback para o texto cru), o gazetteer (que
**tem** fallback para o texto cru), a entrada do BERT (`pipeline._tokens_para_bert`)
e o encaixotador.

## 2. O que foi medido na base

Contexto de cada ocorrência das abreviações suspeitas, nos 23.554 registros
(`DESCRICAO_LONGA` + `DESCRICAO_CURTA`):

| Token | Ocorrências | O que a base quer dizer | Tabela antiga | Decisão |
|---|---|---|---|---|
| `PN` | ~1.900 | `PN 16` (166) e `PN 25` (145) = **pressão nominal**, que são valores do PDM (`CLASSE PRESSAO` de PDM040–043). O resto (`METSO PN 123...`) é part number | `PART NUMBER` | `PN` + pressão da série PN fica `PN`; o resto continua `PART NUMBER` |
| `REV` | 340 | 331 são `REV A` colado a um part number: **revisão** de desenho | `REVESTIDO` | `REV` + token de até 2 caracteres, ou `REV` no fim depois de um código, fica `REV` |
| `RET` | 183 | 33 registros com `VALV`/`VALVULA RET`: válvula de **retenção** (30 trazem o tipo do PDM043: portinhola, pistão, esfera) | `RETENTOR` | depois de válvula vira `RETENCAO`; nos demais casos continua `RETENTOR` |
| `IND` | 61 | depois de `SENSOR` (17) é **indutivo**; depois de `MANG` (44) é industrial | `INDUSTRIAL` | depois de sensor vira `INDUTIVO` |
| `S/` `C/` `P/` | ~1.300 | `S/ACAB` (114), `S/ACABAMENTO` (80), `C/TERMINAIS` (267), `P/N` (789), `P/` (88) | não expandia | `S/` = `SEM`, `C/` = `COM`, `P/` = `PARA`, `P/N` = `PART NUMBER`, `S/N` intocado |
| `CAB` | 759 | 752 são `CAB SEXTAVADA` (cabeça) | não estava na tabela | **mantido sem expansão**: nenhum valor do PDM contém `CABECA`, e o BERT foi treinado vendo `CAB` |
| `CONT` | 63 | misto (contator, contato) | `CONTATOR` | **não mexido**: volume baixo e sem um padrão de vizinhança claro |

## 3. Regressão encontrada durante a implementação

A primeira versão da regra de barra expandia `S/AC` para `SEM AC`. A
`DESCRICAO_CURTA` é truncada em 40 caracteres e corta `S/ACAB` em `S/AC`. O token
solto `AC` casou com o sinônimo `AC → ACO CARBONO`, e o registro `27031887`
(`PARAFUSO SEXTAVADO UNC 1/4"X8POL SAE GRAU 8 S/ACAB`), que não informa material,
ganhou `MATERIAL = ACO CARBONO`. Era um valor inventado.

Correção: o que vem depois da barra só é expandido se for uma abreviação
conhecida ou uma palavra de pelo menos 4 letras. Teste:
`test_barra_truncada_fica_intacta`.

A regressão só apareceu porque a comparação foi feita **registro a registro**.
No agregado ela somava +1 caixa preenchida e passaria como melhora.

**Risco que fica registrado:** o sinônimo `AC → ACO CARBONO` em `sinonimos.py`
continua lá. `AC` também é corrente alternada. Ele não foi alterado nesta mudança,
mas merece revisão.

## 4. Resultado medido

Duas execuções de `04_extrair.py` sobre os 23.554 registros, partindo do mesmo
`aprendizado.json`, comparadas com `scripts/12_comparar_execucoes.py`.

### Só regras (`--sem-bert --sem-llm`)

| Indicador | Antes | Depois |
|---|---|---|
| SANEADO | 10.287 | **10.295** |
| PENDENTE | 11.234 | 11.226 |
| Chaves fechadas | 11.300 | **11.308** |
| Códigos redundantes | 1.396 | 1.396 |
| Caixas que mudaram de valor | — | **0** |

O que mudou:

- **33 válvulas de retenção estavam na classe errada.** 30 estavam como
  válvula esfera (PDM040), 2 como PDM044 e **1 como RETENTOR (PDM032)**. Agora
  as 33 estão em PDM043 (válvula retenção), e 7 delas passaram a SANEADO. Nenhuma
  tinha chave fechada antes, então não havia junção falsa a desfazer, mas o
  catálogo as listava na aba e com as caixas erradas.
- **`PN 16`/`PN 25`: zero efeito nas regras.** O gazetteer já tinha fallback
  para o texto cru e encontrava o valor ali. A correção vale para a classificação
  e para a entrada do BERT (seção abaixo), não para o casamento literal.
- **`S/ACAB`: zero efeito nas regras.** O dicionário aprendido já tinha
  `S/ACAB → SEM ACABAMENTO`. Agora o valor sai do casamento literal, sem depender
  do aprendido.

## 5. Com BERT (`--sem-llm`)

Três execuções sobre os 23.554 registros, com o mesmo código congelado (só o
`texto.py` muda) e o mesmo `aprendizado.json` de partida.

| Indicador | Antes | 1ª versão (`P/N` → `PART NUMBER`) | **Versão final** (`P/N` intacto) |
|---|---|---|---|
| SANEADO | 10.069 | 10.041 (−28) | **10.077 (+8)** |
| PENDENTE | 11.008 | 11.034 | 10.998 |
| Chaves fechadas | 15.614 | 15.623 | 15.622 (+8) |
| Códigos redundantes | 2.111 | 2.109 | 2.111 |

### A segunda regressão: `P/N`

Na primeira versão, `P/N` era expandido para `PART NUMBER`. Isso não muda
nada nas regras, mas muda a **entrada do BERT**, que foi treinado com o texto cru
e nunca viu `PART NUMBER`. Com o contexto novo, o modelo passou a etiquetar a
palavra `FABRICANTE` vizinha (`FAB CATERPILLAR P/N 519-8798`, expandido para
`FABRICANTE CATERPILLAR ...`) como valor de MATERIAL: **47 registros saíram de
SANEADO**. O `P/N` voltou a ficar intacto.

O erro de fundo já existia antes desta mudança: 3.141 registros com `MATERIAL
= "FABRICANTE"` recusado pelo validador. A correção dele está em
`docs/10-correcoes-extracao.md`.

### O que a versão final mudou com BERT

- **410 part numbers deixaram de ser corrompidos:** `N81788A66 REVESTIDO A`
  voltou a ser `N81788A66 REV A`. O `REV` de revisão de desenho virava
  `REVESTIDO` antes de chegar ao BERT.
- **33 válvulas de retenção** foram para PDM043, como no modo só regras.
- **4 caixas esvaziadas** em válvulas com `CL:PN 16`/`CLASSE:PN 25`
  (DIAMETRO NOMINAL) e numa arruela. Com `PN 16` intacto, o BERT recorta o
  diâmetro de outro jeito. São casos isolados, registrados aqui para não se
  perderem.
- 16 registros entraram em SANEADO e 9 saíram (saldo de +8 com os demais).

## 6. Como reproduzir

O jeito seguro é comparar duas **cópias** do código, e não usar `git stash`:
com outras mudanças não commitadas no mesmo arquivo, o stash leva junto o que
não é seu.

```bash
S=/tmp/abrev
for v in antes depois; do mkdir -p $S/cod_$v $S/$v; cp -r scripts src $S/cod_$v/
  ln -sf $PWD/artefatos/pdm.json $S/$v/; ln -sfn $PWD/artefatos/modelo_bert $S/$v/
  cp artefatos/aprendizado.json $S/$v/; done
# edite $S/cod_antes/src/... para a versão antiga, depois:
(cd $S/cod_antes  && $OLDPWD/.venv/bin/python scripts/04_extrair.py --sem-llm --artefatos $S/antes  --base $OLDPWD/dados/01_base_materiais.xlsx)
(cd $S/cod_depois && $OLDPWD/.venv/bin/python scripts/04_extrair.py --sem-llm --artefatos $S/depois --base $OLDPWD/dados/01_base_materiais.xlsx)
.venv/bin/python scripts/12_comparar_execucoes.py $S/antes $S/depois
```

Cada execução precisa partir de uma **cópia** do `aprendizado.json`, porque o
pipeline grava nele durante a execução. Duas execuções com BERT em paralelo
estouram a memória em 30 GB: rode uma de cada vez.

## 7. Fora do escopo desta mudança

- `ZB`, `ZA` e `GF` (acabamentos) continuam na tabela global. Nos contextos
  medidos estão certos, mas o lugar correto deles é `sinonimos.py`, com a trava
  da lista do atributo.
- O treino do BERT (`rotulos.py`) usa o texto **sem** expansão, e a inferência
  usava o texto **com** expansão. Era um train/serve skew que já existia; foi
  corrigido em seguida (`docs/10-correcoes-extracao.md`): o BERT agora recebe o texto
  sem expansão.
