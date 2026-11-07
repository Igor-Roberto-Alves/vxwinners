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
| `RET` | 183 | 66 vêm depois de `VALV`/`VALVULA`: válvula de **retenção** | `RETENTOR` | depois de válvula vira `RETENCAO`; nos demais casos continua `RETENTOR` |
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

### Com BERT (`--sem-llm`)

_ver seção 5_

## 5. Com BERT

PREENCHER

## 6. Como reproduzir

```bash
S=/tmp/abrev; for d in antes depois; do mkdir -p $S/$d
  ln -sf $PWD/artefatos/pdm.json $S/$d/; ln -sfn $PWD/artefatos/modelo_bert $S/$d/
  cp artefatos/aprendizado.json $S/$d/; done
git stash   # código antigo
.venv/bin/python scripts/04_extrair.py --sem-bert --sem-llm --artefatos $S/antes
git stash pop
.venv/bin/python scripts/04_extrair.py --sem-bert --sem-llm --artefatos $S/depois
.venv/bin/python scripts/12_comparar_execucoes.py $S/antes $S/depois
```

Cada execução precisa partir de uma **cópia** do `aprendizado.json`, porque o
pipeline grava nele durante a execução.

## 7. Fora do escopo desta mudança

- `ZB`, `ZA` e `GF` (acabamentos) continuam na tabela global. Nos contextos
  medidos estão certos, mas o lugar correto deles é `sinonimos.py`, com a trava
  da lista do atributo.
- O treino do BERT (`rotulos.py`) usa o texto **sem** expansão, e a inferência
  usa o texto **com** expansão. É um train/serve skew que já existia e não foi
  causado por esta mudança.
