# Prompt: conjunto-ouro das características técnicas, da classe e da junção

Você vai construir o conjunto-ouro (gabarito) que falta no projeto de saneamento de cadastro de materiais em `/home/igor-alves/clas/hack/vxwinners`. O gabarito que já existe (`avaliacao/gold.csv`, avaliado por `evaluate.py`) cobre só quatro campos de cadastro: GRUPO_MERCADORIA, NCM, FABRICANTE e REFERENCIA_FABRICANTE. Falta medir o que o pipeline mais produz: as **características técnicas** de cada item (bitola, comprimento, diâmetro, material, rosca, pressão...), a **classe** do item e a **junção** de duplicados.

Siga o método e o formato do gabarito atual (`avaliacao/00_candidatos.py`, `avaliacao/01_adjudicar.py`, `avaliacao/gold.csv`). Leia esses arquivos antes de começar.

## Regra mais importante: o gabarito tem de ser independente do pipeline

O gabarito existe para medir o pipeline. Se ele copiar o pipeline, mede o pipeline contra ele mesmo.

- **Para anotar, use apenas** `dados/01_base_materiais.xlsx` (o texto cru) e `dados/03_padrao_cadastro_PDM.xlsx` (o padrão: classes, atributos, valores permitidos, formatos, regras de quando um atributo se aplica).
- **Não leia** `artefatos/` (saneado_base.csv, decisoes_base.jsonl, catalogo_final.xlsx, aprendizado.json), nem rode nada de `src/saneamento/` ou `scripts/`, nem leia `docs/07` a `docs/11`, durante a seleção dos candidatos e a anotação. Uma única exceção está na parte C (junção), descrita lá.
- Não chame nenhuma API de LLM externa. A anotação é feita por você.
- Faça **duas anotações independentes** (personas A e B), sem que uma veja a saída da outra, e depois adjudique. O gabarito atual registra kappa 1,0 com zero divergências em 456 rótulos, o que indica que A e B não foram independentes. Desta vez, anote B numa passada separada, sem reabrir o que A escreveu, e com outra ordem de itens. Divergência é esperada e é o que dá valor à adjudicação.

## Parte A: características técnicas (a principal)

**Unidade de anotação:** (item × atributo obrigatório que se aplica àquele item, segundo o PDM). Respeite a coluna QUANDO_SE_APLICA: um atributo condicional só entra quando a condição vale para o item.

**Primeiro rotule a classe** (`ID_PDM`) do item a partir do texto. Os atributos a anotar são os da classe **correta**, não os do GRUPO_MERCADORIA da coluna, que às vezes está errado.

**Status de cada rótulo:**

| Status | Quando | O que o pipeline deveria fazer |
|---|---|---|
| `DEFINIDO` | o texto traz o valor sem ambiguidade | preencher com esse valor |
| `AUSENTE` | o texto não traz o valor | deixar vazio; preencher é **invenção** |
| `INDEFINIVEL` | o texto traz algo, mas não decide entre dois valores (`INOX` para 304 ou 316; `ZINCADO` para branco ou amarelo) | não preencher, ou marcar dúvida; preencher é **invenção** |

**Valor (`y_gold`) no formato canônico do PDM:**
- valor de lista: exatamente como a lista do PDM o escreve;
- milímetro: número + MM, decimal com vírgula (`16,25MM`, `35MM`, sem zero inútil);
- polegada: fração + POL, inteiro separado por ponto (`1/2POL`, `1.1/4POL`);
- pressão: sempre em BAR. Registre também a unidade e o número originais (`evidencia`), porque o avaliador vai comparar grandezas convertidas com tolerância;
- seção de cabo: MM2.

Quando o valor exigir conversão ou interpretação, escreva em `justificativa` o raciocínio de uma linha (`145 PSI / 14,5038 = 10,0 BAR`).

**Armadilhas que o gabarito precisa cobrir**, porque são exatamente onde extratores erram nesta base. Escolha candidatos que as contenham:
- vírgula decimal dentro de valor rotulado: `SECAO:1,5MM2`, `DIAMETRO:16,25MM`;
- polegada escrita com aspas (`2"`), com `IN` (`1 IN`, `3/4 IN`), em fração mista (`1 1/4"`, `1-3/4"`) e decimal (`1,5POL`);
- rosca métrica fina e grossa: `M12X1,5` (bitola fina), `M12X50` (bitola mais comprimento), `M10X1,25X70`, `M8X1,25` (passo grosso escrito), `M16X1M` (barra de 1 metro);
- `PN 16` (pressão nominal, valor do PDM) contra `PN 123456` (part number);
- `CL 150#` e `150#` (classe de pressão);
- unidades que não se convertem sem perda: manômetro em `KGF/CM2` contra `BAR`;
- abreviação ambígua: `VALV RET` (retenção) contra `RET` sozinho (retentor); `SENSOR IND` (indutivo) contra `MANG IND` (industrial); `S/ACAB` (sem acabamento);
- ordem de grandezas sem rótulo: `RETENTOR 90MM 112MM 8MM` (eixo, alojamento e largura);
- descrição curta truncada em 40 caracteres, que corta o último valor (`S/ACAB` virando `S/AC`);
- grupo de mercadoria errado na coluna (um retentor cadastrado em tubos).

**Amostra:** cerca de **240 itens**, estratificada em duas dimensões:
1. **família de classe:** fixadores (parafuso, porca, arruela), vedação (o-ring, retentor, junta), rolamentos, válvulas, conexões de tubulação, elétricos (cabo, disjuntor, contator), mangueiras (avulsa e montada), sobressalentes (PDM110), e uma faixa "outras";
2. **estilo de texto:** estruturado (`ATRIBUTO: VALOR; ...`) contra telegráfico (`PARAF SEXT M12X50 8.8 ZB`).

Garanta pelo menos 8 itens por armadilha da lista acima, e pelo menos 60 rótulos AUSENTE ou INDEFINIVEL no total. Sem esses rótulos não é possível medir invenção. Use semente fixa e registre a regra de seleção, como o `00_candidatos.py` faz.

## Parte B: classe do item

Um rótulo por item: `ID_PDM`, ou `FORA_DO_PDM` quando nenhuma classe serve (nunca force uma classe). Cubra de propósito: classes irmãs que se confundem (válvula esfera, gaveta, globo, retenção, borboleta; rolamento rígido, autocompensador, cônico; parafuso sextavado e sextavado interno; arruela lisa e de pressão; mangueira avulsa e montada), itens com grupo errado na coluna, e itens que não pertencem ao PDM.

## Parte C: junção (pares de códigos)

Rotule pares de códigos como `MESMO_ITEM`, `ITENS_DIFERENTES` ou `INDETERMINADO`. Use o critério do PDM: classe de especificação técnica = todos os obrigatórios iguais; classe de referência (filtros, sobressalentes) = mesmo fabricante e mesmo part number. **Equivalência entre fabricantes não é o mesmo item** (regra 13: `CAT 1R-1808` e `DONALDSON P551808` são intercambiáveis, mas distintos).

Esta é a única parte que pode usar a saída do pipeline, e **só para escolher os pares**, nunca para rotulá-los. Leia `artefatos/saneado_base.csv` apenas para sortear:
- 70 pares de códigos com a mesma `CHAVE_IDENTIDADE` (mede a precisão da junção);
- 50 pares que diferem em exatamente um atributo obrigatório (mede se a diferença é real ou erro de extração);
- 30 pares com descrição muito parecida por palavras, mas chaves diferentes (mede o que a junção deixa passar).

Na anotação, mostre a você mesmo só o texto cru dos dois códigos, sem chave, sem cluster e sem a fonte do par.

## Entregáveis

Em `avaliacao/`, sem alterar o que já existe:

1. `10_candidatos_caracteristicas.py`: seleção reproduzível (semente, regras, estratos).
2. `candidatos_caracteristicas.csv` e `pares_juncao_candidatos.csv`.
3. `anotacoes_carac_A.jsonl` e `anotacoes_carac_B.jsonl` (uma linha por rótulo: CODIGO_MATERIAL, id_pdm, campo, y_gold, status, evidencia, justificativa).
4. `11_adjudicar_caracteristicas.py`: igual ao `01_adjudicar.py`. Cada divergência exige uma decisão escrita do adjudicador, e o script aborta se faltar alguma.
5. `gold_caracteristicas.csv` (mesmas colunas do `gold.csv`: CODIGO_MATERIAL, estrato, campo, y_gold, status, evidencia, justificativa, anot_A, anot_B, origem_decisao, confianca), mais `gold_classe.csv` e `gold_juncao.csv`.
6. `concordancia_caracteristicas.json`: acordo bruto e kappa de Cohen por atributo e global.
7. `evaluate_caracteristicas.py`: avalia o pipeline lendo `artefatos/decisoes_base.jsonl` e `artefatos/saneado_base.csv`, e gera um `.md` com:
   - precisão (IC 95% de Wilson), cobertura e **taxa de invenção** (preencheu em AUSENTE ou INDEFINIVEL) por atributo, por família de classe, por estilo de texto e por armadilha;
   - o mesmo recorte **por fonte do valor** (campo `fonte` de cada decisão: rotulo, gazetteer, sinonimo, aprendido, gramatica, bert, llm...). Isso diz qual camada erra;
   - acerto de classe, com matriz de confusão entre as classes irmãs;
   - precisão e recall da junção;
   - a lista anotada de cada erro e de cada invenção.

   Compare grandezas numericamente: `35,0MM` = `35MM`, e pressão convertida com tolerância de 1%. Compare valores de lista após normalizar maiúsculas e acentos.
8. `GABARITO_CARACTERISTICAS.md`: método, tamanhos, estratos, kappa, limitações, e quanto tempo a conferência humana levaria.

## Conferência humana

Você é um LLM, e um gabarito feito só por LLM tem viés próprio. Deixe pronta, para uma pessoa do time, uma planilha `revisao_humana_caracteristicas.csv` com: todos os rótulos INDEFINIVEL, todas as divergências adjudicadas e uma amostra aleatória de 10% dos demais, com colunas para a pessoa marcar `concordo`/`discordo` e o valor certo. Quando ela devolver, o adjudicador incorpora as correções e regera o `gold_caracteristicas.csv`.

## Critério de pronto

- 240 itens anotados, com pelo menos 60 rótulos AUSENTE ou INDEFINIVEL e todas as armadilhas cobertas;
- `gold_classe.csv` cobre os 240 itens e `gold_juncao.csv` tem 150 pares;
- os dois scripts de adjudicação e avaliação rodam sem erro (use `uv run --no-project --with pandas --with openpyxl python ...`, porque o `.venv` não tem pandas);
- o `.md` de avaliação foi gerado ao menos uma vez sobre os artefatos atuais;
- nenhum arquivo fora de `avaliacao/` foi alterado.
