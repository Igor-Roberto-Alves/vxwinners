# Efeito do piso de probabilidade por palavra no BERT

Gabarito: `gold_caracteristicas.csv` — 1131 rótulos em 232 códigos.
Pipeline reexecutado por piso, sem LLM, dicionário congelado; desempates e
detecções do artefato aplicados, como na execução de referência.

| piso | precisão | IC 95% | cobertura | invenção | acerto | erro | absteve | invenção |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 0.00 | 98.7% | 98%–99% | 90.4% | 6.0% | 935 | 12 | 100 | 5 |
| 0.50 | 98.7% | 98%–99% | 90.3% | 6.0% | 933 | 12 | 102 | 5 |
| 0.80 | 98.8% | 98%–99% | 90.2% | 6.0% | 933 | 11 | 103 | 5 |

## Diferença contra o piso 0,00 (comportamento atual)

| piso | Δ precisão | Δ cobertura | Δ erros | Δ abstenções | Δ invenções |
|---:|---:|---:|---:|---:|---:|
| 0.50 | -0.0% | -0.2% | +0 | +2 | +0 |
| 0.80 | +0.1% | -0.3% | -1 | +3 | +0 |

## Campos sem enum (part number, modelo) e ruído para o canonizador

Nos campos de código o validador não tem lista para recusar nada: o corte de
probabilidade é a única trava. A última coluna conta o trecho que o BERT recortou
e o enum recusou — não é erro contra o gabarito, é trabalho que o LLM paga depois.

| piso | precisão nos campos de código | afirmados | trechos recusados pelo enum |
|---:|---:|---:|---:|
| 0.00 | 91.7% | 36 | 3 |
| 0.50 | 91.7% | 36 | 1 |
| 0.80 | 94.3% | 35 | 1 |

## Alcance fora do gabarito

Amostra aleatória de 2000 registros (semente 42), fora do gabarito.

`trocou` é o efeito que não era esperado: quando o piso derruba o recorte do
BERT, a caixa não fica vazia — outra camada (regra léxica, ordem do PDM,
dicionário) assume e pode gravar um valor DIFERENTE. O piso muda quem decide,
não só quanto se afirma.

| piso | decisões que mudaram | registros afetados | sumiram | trocaram | (destas, encurtaram) | surgiram |
|---:|---:|---:|---:|---:|---:|---:|
| 0.00 | — (referência) | — | — | — | — | — |
| 0.50 | 12 | 12 | 9 | 3 | 2 | 0 |
| 0.80 | 42 | 41 | 34 | 7 | 4 | 1 |

Exemplos com piso 0.50:

- a caixa ficou vazia · `21469786` · COMPRIMENTO EXTERNO: `2577MM` → `(vazio)`
- a caixa ficou vazia · `29364932` · DIAMETRO INTERNO: `3/8POL` → `(vazio)`
- a caixa ficou vazia · `24551474` · DIAMETRO INTERNO: `1POL` → `(vazio)`
- a caixa ficou vazia · `14864764` · LARGURA: `46MM` → `(vazio)`
- a caixa ficou vazia · `16146186` · CORRENTE NOMINAL: `25A` → `(vazio)`
- outra camada assumiu e gravou outro valor · `27171168` · DIAMETRO EIXO: `165MM` → `10MM`
- outra camada assumiu e gravou outro valor · `26474929` · DIAMETRO: `230MM` → `22,23MM`
- outra camada assumiu e gravou outro valor · `27822915` · PRESSAO TRABALHO: `17,24BAR` → `24,5BAR`

Exemplos com piso 0.80:

- a caixa ficou vazia · `27183467` · ESPESSURA: `8MM` → `(vazio)`
- a caixa ficou vazia · `21469786` · COMPRIMENTO EXTERNO: `2577MM` → `(vazio)`
- a caixa ficou vazia · `10355709` · REFERENCIA: `6007-C3` → `(vazio)`
- a caixa ficou vazia · `14310041` · SECAO: `5MM` → `(vazio)`
- a caixa ficou vazia · `11594435` · ESPESSURA: `1,6MM` → `(vazio)`
- outra camada assumiu e gravou outro valor · `19781364` · FAIXA: `0-2,5BAR` → `2,5BAR`
- outra camada assumiu e gravou outro valor · `27171168` · DIAMETRO EIXO: `165MM` → `10MM`
- outra camada assumiu e gravou outro valor · `28261083` · FAIXA: `0-25BAR` → `24,5BAR`
- outra camada assumiu e gravou outro valor · `26474929` · DIAMETRO: `230MM` → `22,23MM`
- outra camada assumiu e gravou outro valor · `24560074` · REFERENCIA FABRICANTE: `B2987-00 LUBR` → `B2987-00`

## De onde vêm os erros e as invenções que sobram

- piso 0.00: `gazetteer` 5, `bert` 3, `ordem_pdm` 3, `aprendido` 3, `rotulo` 1, `dominio` 1
- piso 0.50: `gazetteer` 5, `bert` 3, `ordem_pdm` 3, `aprendido` 3, `rotulo` 2, `dominio` 1
- piso 0.80: `gazetteer` 5, `ordem_pdm` 3, `aprendido` 3, `bert` 2, `rotulo` 2, `dominio` 1
