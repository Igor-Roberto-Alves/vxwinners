# Valor financeiro da duplicidade, como faixa

Gerado por `avaliacao/30_valor_financeiro.py` sobre `/home/igor-alves/clas/hack/vxwinners/artefatos/plano_juncao.csv`.
Precisão da junção: gabarito da juncao (gold_juncao.csv).

| | Valor |
|---|---|
| Capital em código redundante, somando todas as junções | R$ 30,24 mi |
| **Capital ajustado pela precisão medida** | **R$ 30,23 mi** |
| **Faixa (IC 95%)** | **R$ 26,50 mi a R$ 30,24 mi** |
| Parte que não depende de nenhuma conclusão do LLM | R$ 29,40 mi (R$ 25,73 mi a R$ 29,40 mi) |
| Capital em clusters que dependem do LLM (bruto) | R$ 0,84 mi |

## Por estrato

| Tipo | LLM | Tamanho | Clusters | Capital bruto | Rótulos | Precisão | IC 95% | Nota |
|---|---|---|---|---|---|---|---|---|
| referencia | com_llm | 2 | 8 | R$ 0,22 mi | 2 | 98.5% | 91.9–99.7% | herdada do total |
| referencia | com_llm | 3+ | 7 | R$ 0,11 mi | 0 | 98.5% | 91.9–99.7% | herdada do total |
| referencia | sem_llm | 2 | 769 | R$ 13,19 mi | 23 | 100.0% | 85.7–100.0% |  |
| referencia | sem_llm | 3+ | 297 | R$ 14,95 mi | 10 | 100.0% | 89.6–100.0% | herdada de referencia/sem_llm |
| tecnica | com_llm | 2 | 242 | R$ 0,27 mi | 4 | 98.5% | 91.9–99.7% | herdada do total |
| tecnica | com_llm | 3+ | 95 | R$ 0,24 mi | 7 | 98.5% | 91.9–99.7% | herdada do total |
| tecnica | sem_llm | 2 | 455 | R$ 0,88 mi | 17 | 100.0% | 81.6–100.0% |  |
| tecnica | sem_llm | 3+ | 118 | R$ 0,38 mi | 3 | 100.0% | 83.9–100.0% | herdada de tecnica/sem_llm |

## Frase para o pitch

> Entre R$ 26,50 mi e R$ 30,24 mi em capital parado em código duplicado (IC 95%), dos quais R$ 29,40 mi vêm de junções que não dependem de nenhum modelo de linguagem.

## Limites

- A conta usa a precisão da junção, não o recall: duplicidade que o pipeline não achou não está aqui.
- O capital é estoque × preço médio do ERP, sem ajuste de obsolescência.
- Estrato com poucos rótulos herda a precisão do estrato-pai (coluna Nota).
