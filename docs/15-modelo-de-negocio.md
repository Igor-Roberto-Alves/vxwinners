# Modelo de negócio e tamanho de mercado

> **Como ler.** Segue a convenção da [`03-analise-mercado.md`](03-analise-mercado.md): 🟢 é **medido**
> nesta base e reproduzível; 🟡 é **premissa** nossa, com a conta aberta; 🔵 é **fonte externa**, com
> link na seção 9. A 03 diagnostica o problema. Este documento responde à pergunta seguinte: como isso
> vira empresa, e de que tamanho.
>
> Os números vêm de `artefatos/radar.json`, `artefatos/plano_juncao.csv`, das rodadas em
> `artefatos/medicao_pedidos/` e do gerador `avaliacao/17_slides_mercado_html.py`, que tem todas as
> premissas num dicionário só (`PREMISSA`). Trocou uma premissa, rode o gerador: os slides acompanham.

---

## 1. A proposta em uma página

**O que vendemos.** Uma camada que lê o texto livre do cadastro de materiais, preenche os atributos
contra o padrão do próprio cliente (o PDM) e decide duplicidade por **igualdade de chave**, não por
semelhança de texto. Ela funciona em dois momentos: limpa a base que existe e barra o erro no pedido
que está chegando.

**Para quem.** Indústria pesada multiplanta no Brasil, com mais de ~10 mil materiais cadastrados e
estoque grande de sobressalentes: mineração, energia, óleo e gás, siderurgia, celulose, saneamento.

**Como cobramos.** Três receitas, em fases:

| Fase | Receita | Natureza | Na Serra Azul 🟡 |
|---|---|---|---|
| 1 | **Saneamento** da base | projeto, uma vez | R$ 353 mil (23.554 registros × R$ 15) |
| 2 | **Modo de cadastro**, com a ponte entre plantas | assinatura | R$ 240 mil/ano (R$ 20 mil/mês) |
| 3 | **Rede entre empresas**: a sobra de um cliente vira oferta para outro | comissão por transação | depende de vários clientes |

**Por que o cliente paga.** A ferramenta acha **R$ 30,24 mi** de capital consolidável, que é **15,1%**
do estoque 🟢. Esse capital custa **R$ 9,07 mi por ano** parado, a 30% a.a. 🟡. O cliente paga
R$ 593 mil no primeiro ano e recupera **15 vezes** isso. O preço se paga em menos de um mês 🟡.

**Tamanho.** SAM de **R$ 48 mi/ano** em assinatura, mais R$ 71 mi em projetos (200 empresas) 🟡.
SOM de **R$ 2,4 mi/ano** no ano 3 (10 clientes) 🟡. A categoria em que competimos (MDM, gestão de
dados mestres) movimenta cerca de **US$ 18,6 bi/ano** no mundo 🔵.

**O que diferencia.** Lê português industrial abreviado. Decide duplicidade por chave auditável,
inclusive equivalência ≠ duplicidade. Prefere pendência a palpite. Quase não pesa no custo: os
520 pedidos com todas as camadas ligadas custaram **US$ 0,30** de LLM 🟢.

---

## 2. Tudo o que dá para fazer: o leque de modelos

Antes da proposta, as opções. Cada uma foi pesada pelo que a base e as medições mostram.

### 2.1 Formas de cobrar

| Modelo | Como funciona | A favor | Contra | Veredito |
|---|---|---|---|---|
| **Projeto por registro** | preço por material saneado | fácil de orçar; o cliente compara com consultoria | receita acaba quando a base termina | **sim, como porta de entrada** |
| **Taxa de sucesso** | % do capital liberado comprovado | alinha ao resultado; dispensa discutir preço de software | o capital só é liberado quando o cliente baixa o estoque, o que pode levar meses e depende de política contábil | **opcional**, para quem resiste ao preço fixo |
| **Assinatura (SaaS)** | mensalidade pelo modo de cadastro | receita recorrente e previsível; protege o ganho do saneamento | precisa provar valor contínuo | **sim, é o contrato** |
| **Por pedido de cadastro** | preço por item cadastrado | escala com o uso; bom para clientes pequenos | receita oscila; o cliente pode economizar pedido | **variante** da assinatura para quem tem pouco volume |
| **Licença instalada (on-premise)** | roda no ambiente do cliente | atende a TI que não aceita nuvem | implantação cara, atualização lenta | **só sob demanda** |
| **API por chamada** | integradores pagam por registro processado | alcance via parceiros | margem menor, sem relação com o cliente final | **fase posterior** |
| **Comissão de rede** | % das transações entre empresas | efeito de rede, que vira fosso competitivo | precisa de muitos clientes na mesma região; poucas transações, de valor alto | **visão, fase 3** |
| **BPO com IA** | nós operamos o cadastro do cliente | receita maior por cliente | vira empresa de serviço, com margem de serviço | **não** |

### 2.2 Produtos que a mesma tecnologia permite

1. **Saneamento da base.** Classe, atributos, descrição no padrão, NCM e plano de junção (R$ 30,24 mi,
   2.676 códigos a bloquear em 1.991 grupos) 🟢.
2. **Modo de cadastro.** O pedido chega por portal, e-mail ou planilha e sai aprovado, devolvido com a
   lista do que falta, marcado como "já existe" ou como fora do PDM. No gabarito de pedidos: 97,5% de
   classe e 99,1% de precisão nas caixas, com todas as camadas 🟢.
3. **Ponte entre plantas.** Mostra o item parado numa planta enquanto outra, zerada, vai comprar.
   **R$ 1,08 a 2,26 mi** só na Serra Azul, em 66 a 74 itens. O maior caso é um tambor de retorno
   Continental de R$ 780 mil parado no CD com a mina zerada 🟢.
4. **Saneamento fiscal.** NCM preenchido e corrigido: 1.104 trocados contra a tabela vigente 🟢. A
   reforma tributária (CBS/IBS) aumenta o custo de NCM errado.
5. **Radar de compras.** O mesmo item comprado por códigos diferentes, a preços diferentes. A 03
   mediu R$ 1,19 mi de dispersão de preço dentro dos grupos 🟢.
6. **Rede entre empresas** (fase 3). A sobra de um cliente vira oferta para outro, porque a chave de
   identidade torna os estoques comparáveis.
7. **Catálogo de referência** (fase 3). Cada cliente novo enriquece o dicionário de fabricantes,
   part numbers e traduções. O LLM já cria regras de tradução de classe a partir de catálogo em inglês
   (11 regras, US$ 0,13) 🟢. Com vários clientes, isso vira um ativo que ninguém tem em português.

---

## 3. A proposta: saneamento abre, cadastro segura, rede multiplica

### 3.1 Por que essa combinação

Os dados da base decidem a forma do negócio:

- **O problema é um fluxo, não um passivo.** A base recebe **cerca de 1.030 cadastros novos por ano**,
  constante de 2021 a 2025, feitos por 260 pessoas diferentes 🟢. Quem só saneia entrega o ganho uma
  vez, e a base volta a sujar. Por isso a assinatura é o contrato e o saneamento é a venda.
- **O valor está concentrado.** Sobressalentes e filtros são 37% dos registros e 84% do valor do
  estoque 🟢. O piloto deve atacar essas duas classes primeiro, porque é onde o dinheiro aparece na
  primeira reunião.
- **O ganho é medido antes de contratar.** O diagnóstico roda sobre a base do cliente e entrega o
  número dele: quantos códigos redundantes, quanto capital, quais itens. A venda vira uma conversa
  sobre um número, não sobre software.

### 3.2 Jornada do cliente

| Etapa | O que acontece | Prazo 🟡 | Receita |
|---|---|---|---|
| **Diagnóstico** | o cliente envia a extração da base; devolvemos o placar: capital consolidável, ponte entre plantas, NCM exposto | 2 semanas | gratuito ou simbólico, abatido do projeto |
| **Saneamento** | base inteira no padrão, plano de junção, fila de intervenção para o time do cliente decidir | 2 a 3 meses | projeto por registro |
| **Cadastro** | todo pedido novo passa pela ferramenta antes de virar código no ERP | contínuo | assinatura |
| **Expansão** | mais plantas, outras empresas do grupo, radar de compras | contínuo | assinatura maior |
| **Rede** | com clientes suficientes na mesma região, abre a troca entre empresas | fase 3 | comissão |

### 3.3 Preço 🟡

| Item | Preço proposto | Âncora |
|---|---|---|
| Saneamento | **R$ 15 por registro** | o valor consolidável medido é de R$ 1.284 por registro 🟢; o preço é 1,2% disso |
| Assinatura | **R$ 20 mil/mês** para 6 plantas | menos de 3% do custo de oportunidade anual do capital encontrado |
| Taxa de sucesso (alternativa) | 5 a 10% do capital efetivamente liberado | só sobre o que o cliente baixar no ERP |
| Rede (fase 3) | 5% por transação | a validar com os primeiros clientes |

**Atenção:** nenhum desses preços foi validado com comprador real. Pela conta da assinatura dividida
por ~1.030 cadastros/ano, cada item cadastrado sai a ~R$ 233. Esse número precisa ser comparado com o
custo de hoje: horas de analista por item, mais retrabalho e duplicatas. Essa é a primeira pergunta
para as entrevistas da seção 8.

### 3.4 Custo de operar (unit economics)

| Item | Medido 🟢 |
|---|---|
| 12.909 fabricantes preenchidos por LLM | US$ 20,45 |
| 520 pedidos com BERT + LLM + regras de classe | US$ 0,30, menos de US$ 0,001 por pedido |
| Benchmark inteiro (10 soluções × 4 campos) | US$ 173,62 |
| Reexecução completa, depois da primeira vez | segundos, porque as respostas ficam em cache e viram regra de dicionário |

O custo de IA é desprezível frente ao preço. O custo real do negócio é de **gente**: implantação,
adaptação ao PDM de cada cliente e atendimento. A margem bruta da assinatura deve ficar no padrão de
software, e a do projeto de saneamento no padrão de serviço com ferramenta 🟡.

### 3.5 Para quem vender: comprador e usuário

- **Quem assina:** diretoria de Suprimentos ou CFO, por causa do capital parado e do risco fiscal.
- **Quem usa:** o time de cadastro de materiais e o almoxarifado.
- **Quem pode vetar:** TI (integração com o ERP, normalmente SAP) e o Fiscal (NCM).
- **Canal:** venda direta para os primeiros 10 clientes. Depois, parcerias com consultorias de SAP e
  integradores, que já têm a relação e hoje vendem saneamento manual.

---

## 4. Valor para o cliente, com os números da Serra Azul

| | Valor | Tipo |
|---|---:|---|
| Estoque total | R$ 200,87 mi | 🟢 |
| Capital consolidável (códigos redundantes) | **R$ 30,24 mi · 15,1%** | 🟢 |
| Custo de oportunidade desse capital | R$ 9,07 mi/ano (30% a.a.) | 🟡 |
| Ponte entre plantas | R$ 1,08 a 2,26 mi | 🟢 |
| NCM corrigido | 1.104 itens | 🟢 |
| Preço no ano 1 | R$ 593 mil | 🟡 |
| **Retorno no ano 1** | **15×**, payback de 0,8 mês | 🟡 |

**Ressalva que deve ser dita na banca:** a Serra Azul é fictícia. Todo número medido vale nesta base.
O que se leva a outro cliente é o método, e a razão de 15,1% serve como **primeira estimativa** do
ganho de qualquer empresa ("multiplique pelo seu estoque"). Fontes de mercado apontam duplicidade de
10 a 20% do estoque em operações multiplanta 🔵 (Verusen) e de 5 a 7% das compras de MRO 🔵
(Verdantis). As duas são de fornecedores, mas a nossa razão cai dentro da faixa.

---

## 5. Tamanho de mercado

### 5.1 Método

De baixo para cima: **número de empresas no perfil × receita por cliente**. O número de cima para
baixo (relatório de mercado de MDM) entra só como contexto da categoria, nunca como o nosso mercado.
Uma banca com gente de suprimentos derruba TAM inflado na primeira pergunta.

### 5.2 TAM, SAM e SOM

| | Valor | Como chegamos | Tipo |
|---|---:|---|---|
| **TAM** | **US$ 18,6 bi/ano** | mercado global de gestão de dados mestres (MDM), 2025. É a categoria, não o nosso alcance. Os institutos divergem: de US$ 5 bi a 23 bi | 🔵 |
| **SAM** | **R$ 48 mi/ano** + R$ 71 mi em projetos | 200 industriais multiplanta no Brasil × R$ 240 mil/ano de assinatura, mais 200 × R$ 353 mil de saneamento | 🟡 |
| **SOM** | **R$ 2,4 mi/ano** no ano 3 + R$ 3,5 mi em projetos acumulados | 10 clientes: 2 pilotos no ano 1, 5 no ano 2, 10 no ano 3 | 🟡 |

**Por que o SAM é piso.** O preço usado é o de uma empresa do porte da Serra Azul (R$ 200 mi em
estoque). As maiores são dezenas de vezes maiores:

| Empresa | Estoque de materiais (31/12/2024) | Tamanho em Serras Azuis |
|---|---:|---:|
| Petrobras · materiais, suprimentos e outros | R$ 8,39 bi 🔵 | 42× |
| Vale · estoque de consumo | US$ 988 mi 🔵 | ~30×, conforme o câmbio |

Um cliente desse porte paga por registro e por planta. Sozinho, pode valer mais que o SOM inteiro.

### 5.3 Sensibilidade: o que muda o SAM

Receita recorrente anual (só assinatura), variando as duas premissas mais frágeis:

| Empresas no perfil ↓ / assinatura → | R$ 10 mil/mês | **R$ 20 mil/mês** | R$ 40 mil/mês |
|---|---:|---:|---:|
| 100 | R$ 12 mi | R$ 24 mi | R$ 48 mi |
| **200** | R$ 24 mi | **R$ 48 mi** | R$ 96 mi |
| 400 | R$ 48 mi | R$ 96 mi | R$ 192 mi |

Mesmo no canto mais pessimista (100 empresas, R$ 10 mil/mês), há espaço para uma empresa de
R$ 2 a 3 mi/ano de receita recorrente com 10 a 20 clientes.

### 5.4 Uma segunda forma de medir: o valor em jogo

Outra conta, útil para o pitch e não para receita: **estoque de materiais das empresas-alvo × 15,1%**.
Só Petrobras e Vale somam mais de R$ 14 bi em materiais de manutenção 🔵. A 15,1%, isso daria
**R$ 2 bi de capital consolidável em duas empresas**. É hipótese, porque a razão vem de uma base
fictícia, mas mostra a ordem de grandeza do problema que o cliente tem.

### 5.5 A rede entre empresas muda o teto

A fase 3 abre um mercado diferente: o **estoque excedente que circula entre empresas**. O teto deixa
de ser o preço da assinatura e passa a ser o volume transacionado. Ainda não há como medir esse
volume sem clientes reais. Na Serra Azul, a ponte interna já mostra a mecânica (R$ 1,08 a 2,26 mi).
Isso fica como visão no pitch, nunca como número de receita.

---

## 6. Concorrência e posicionamento

| Alternativa | O que faz | O que falta |
|---|---|---|
| SAP MDG e módulos de ERP | fluxo de aprovação do cadastro | garante que o campo foi preenchido, não que está certo; não lê texto livre |
| Informatica, Stibo e plataformas de MDM | governam, versionam e casam registros | o casamento é por similaridade de texto, que acha 0 dos 2 grupos de duplicidade plantados no gabarito 🟢 |
| Especialistas em peças (Verdantis, Verusen, SPARETECH) | limpeza e enriquecimento de MRO com IA | foco em inglês e catálogo global; sem NCM nem o PDM do cliente. Provam que há quem pague: a SPARETECH captou Série A com a Insight Partners 🔵 |
| Consultoria e BPO de cadastro | equipe limpa a base | resolve o passivo e vai embora |

**Posicionamento:** não somos uma plataforma de MDM. Somos a **camada de leitura que falta na frente**
de qualquer MDM: texto industrial em português vira atributo tipado, e só então a chave decide
duplicidade. Isso torna o produto complementar ao SAP do cliente, não concorrente. É um argumento
de venda importante, porque ninguém troca de ERP.

**Por que agora:** ler `FILTRO P551808 DONALDSON` e separar part number de fabricante era trabalho
de especialista. Com modelos de linguagem restritos à lista do PDM, custa centavos e pode ser medido
em gabarito.

---

## 7. Riscos e as perguntas que a banca vai fazer

| Pergunta | Resposta |
|---|---|
| "Os números são de uma empresa fictícia." | Sim, e por isso vendemos o método e a razão de 15,1%, não o número absoluto. O diagnóstico de 2 semanas produz o número real de cada cliente antes de ele pagar. |
| "Por que o SAP não faz isso?" | O SAP garante o fluxo, não a leitura do texto. Somos complementares: entregamos o registro limpo para dentro do SAP. |
| "Capital consolidável não é economia." | Correto. É capital **identificado**. Vira caixa quando o cliente baixa o estoque, e por isso a taxa de sucesso é opcional e só incide sobre o que for liberado. |
| "E se o LLM errar?" | Ele só escolhe dentro da lista fechada do PDM; tudo passa por validador; e o que fica em dúvida vai para a fila humana. Precisão medida nas caixas: 99,1% 🟢. |
| "Como escala para outro cliente?" | O PDM é configuração, não código. O que muda é a lista de classes e atributos do cliente. As regras aprendidas (dicionário e traduções de classe) se acumulam entre clientes. |
| "Quanto tempo leva para vender?" | Venda industrial é lenta (meses). Por isso o diagnóstico gratuito: encurta a decisão para uma conversa sobre um número. |
| "A rede entre empresas é realista?" | Começa entre plantas do mesmo grupo, onde não há problema de concorrente expor estoque. Entre empresas, só na fase 3. |

**Riscos reais:**
- **Preço não validado.** Mitigação: entrevistas antes de qualquer número final (seção 8).
- **Ciclo de venda longo.** Mitigação: diagnóstico gratuito e piloto restrito a sobressalentes.
- **Dependência de integração com o ERP.** Mitigação: começar exportando planilha e entrar no SAP depois.
- **Gabarito provisório.** As duas anotações foram de um LLM. A revisão humana precisa voltar antes
  de qualquer número ir para contrato.

---

## 8. O que falta para o modelo ficar defensável

Em ordem de impacto:

1. **Contar as empresas do SAM.** Filtrar o Valor 1000 (ou a lista da B3) pelos setores do perfil e
   pelo critério de ser multiplanta. Hoje as 200 são premissa.
2. **Validar o preço com 3 a 5 compradores.** Perguntas: quanto custa hoje cadastrar um item; quanto
   pagariam por um diagnóstico; preferem preço fixo ou taxa de sucesso.
3. **Tirar o estoque de materiais de 10 empresas abertas** das notas explicativas (B3/CVM), para trocar
   o "porte Serra Azul" por uma distribuição real de tamanhos de cliente.
4. **Custo de parada.** Os 307 grupos com um código com saldo e outro zerado são o risco de máquina
   parada esperando peça que já existe 🟢. Com o custo-hora de parada de uma mineradora, esse vira o
   maior número do pitch.
5. **Revisão humana do gabarito**, para os números de qualidade deixarem de ser provisórios.

---

## 9. Fontes externas

- Mercado de MDM: [Fortune Business Insights](https://www.fortunebusinessinsights.com/master-data-management-market-114277) · [Research and Markets](https://www.researchandmarkets.com/reports/6187021/master-data-management-market-outlook-market)
- Petrobras, estoques em 31/12/2024: [6-K do 4T24](https://www.sec.gov/Archives/edgar/data/1119639/000129281425000670/pbrfs4q24rs_6k.htm) · [20-F 2024](https://www.sec.gov/Archives/edgar/data/1119639/000129281425001352/pbrform20f_2024.htm)
- Vale, estoques em 31/12/2024: [20-F 2024, nota 13](https://www.sec.gov/Archives/edgar/data/917851/000129281425001137/valeform20f_2024.htm)
- Duplicidade em estoque de peças: [Verusen](https://verusen.com/blog/how-ai-identifies-duplicate-mro-materials-across-complex-enterprises/) · [Verdantis](https://www.verdantis.com/?p=40990) (dados de fornecedores)
- Série A da SPARETECH: [Insight Partners](https://www.insightpartners.com/ideas/sparetech-secures-series-a-funding-led-by-us-based-insight-partners-to-fuel-international-expansion/)

Consultadas em 08/11/2026.
