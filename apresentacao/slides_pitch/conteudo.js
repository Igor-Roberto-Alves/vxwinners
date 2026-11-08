/* =====================================================================
   CONTEUDO DO DECK — edite aqui os textos (principalmente os nomes do
   time em `time.membros`). O index.html monta os slides a partir deste
   objeto; nenhum numero deve ser alterado sem conferir a fonte.
   ===================================================================== */
window.CONTEUDO = {
  capa: {
    titulo: "Catálogo MRO inteligente",
    sub: "Cadastro e saneamento de materiais com IA",
    assinatura: "equipe vxwinners · Hackathon VX",
  },

  indice: {
    titulo: "Índice",
    itens: [
      "Problema",
      "Como funciona",
      "Evidência (benchmark)",
      "Dinheiro na mesa",
      "Demo",
      "Mercado",
      "Time",
    ],
  },

  problema: {
    etiqueta: "01 · Problema",
    titulo: "A base que todos usam e ninguém confia",
    cartoes: [
      {
        icone: "capital",
        titulo: "Capital parado",
        texto: "Mesmo item com vários códigos — 9–25% das bases são duplicatas.",
      },
      {
        icone: "compra",
        titulo: "Compra fragmentada",
        texto: "Sem escala — R$ 12,0 mi negociáveis em conjunto.",
      },
      {
        icone: "operacao",
        titulo: "Operação parada",
        texto: "Compra emergencial custa 2–3x.",
      },
      {
        icone: "fiscal",
        titulo: "Risco fiscal",
        texto: "NCM errado — multa de 1%; R$ 9,5 mi expostos.",
      },
    ],
    rodape:
      "Na base do desafio: 23.554 itens · R$ 200,9 mi em estoque · 79% fora do padrão PDM · 66,5% sem fabricante",
  },

  comoFunciona: {
    etiqueta: "02 · Como funciona",
    titulo: "LLM só onde ela paga o próprio custo",
    passos: [
      { n: "1", titulo: "Dados do ERP", texto: "23.554 itens" },
      { n: "2", titulo: "Motor híbrido", texto: "regras + ML clássico + LLM no resíduo" },
      { n: "3", titulo: "Sugestão em ~19 ms", texto: "grupo, NCM, fabricante, part number + alerta de duplicata" },
      { n: "4", titulo: "Pessoa decide", texto: "fila de revisão; nada entra sem validação" },
    ],
    sub: "Determinístico e auditável: cada valor com origem e confiança",
  },

  evidencia: {
    etiqueta: "03 · Evidência",
    titulo: "Medido, auditado e com barra de erro",
    medidores: [
      { campo: "Grupo", valor: "96,5%", pct: 96.5, nota: "teto do gabarito" },
      { campo: "NCM", valor: "91,1%", pct: 91.1, nota: "top-1 · 99,0% top-3" },
      { campo: "Fabricante", valor: "84,3%", pct: 84.3, nota: "acerto exato" },
      { campo: "Part number", valor: "84,4%", pct: 84.4, nota: "acerto exato" },
    ],
    faixa:
      "Conjunto-ouro com dupla anotação: precisão 96,2% [94–98%] · 24.575 campos preenchidos por US$ 21 · Fable 5 (modelo mais caro) testado e não lidera nenhum campo",
  },

  dinheiro: {
    etiqueta: "04 · Dinheiro na mesa",
    titulo: "R$ 101,2 mi destravados para deduplicação",
    // valores em R$ milhões — barra horizontal, uma matiz lavanda
    barras: [
      { rotulo: "Estoque travado", valor: 31.4, texto: "R$ 31,4 mi" },
      { rotulo: "Capital em código duplicado", valor: 3.9, texto: "R$ 3,9 mi" },
      { rotulo: "Dispersão de preço", valor: 1.2, texto: "R$ 1,2 mi" },
      { rotulo: "Negociável em conjunto", valor: 12.0, texto: "R$ 12,0 mi" },
      { rotulo: "Exposição fiscal", valor: 9.5, texto: "R$ 9,5 mi", risco: true },
    ],
    riscoNota: "risco, não economia direta",
    destaque: {
      titulo: "Economia recorrente",
      valor: "R$ 5,7–27 mi/ano",
      nota: "empresa com estoque MRO de R$ 200 mi",
    },
  },

  demo: {
    etiqueta: "05 · Demo",
    titulo: "A demo, ao vivo",
    sub: "Sugestão em ~19 ms sobre a base completa · funciona offline",
    mockup: "img/mockup_demo.png",
  },

  mercado: {
    etiqueta: "06 · Mercado",
    titulo: "Mercado que já paga por isso",
    colunas: [
      {
        sigla: "TAM",
        titulo: "MDM global",
        texto: "US$ 21,6 bi (2026) → US$ 50,9 bi (2031)",
      },
      {
        sigla: "SAM",
        titulo: "Brasil asset-intensive",
        texto: "mineração R$ 298,8 bi de faturamento + 42 distribuidoras + saneamento R$ 29,1 bi/ano",
      },
      {
        sigla: "SOM",
        titulo: "ano 3",
        texto: "40 contas × R$ 400 mil = R$ 16 mi ARR",
      },
    ],
    rodape:
      "CEMEX US$ 16 mi · Bruce Power US$ 42 mi identificados · PiLog mineração US$ 30–35 mi (resultados divulgados pelos fornecedores)",
  },

  time: {
    etiqueta: "07 · Time",
    titulo: "Equipe vxwinners",
    // >>> TROQUE OS NOMES AQUI <<<
    membros: [
      { nome: "Nome 1", funcao: "função" },
      { nome: "Nome 2", funcao: "função" },
      { nome: "Nome 3", funcao: "função" },
      { nome: "Nome 4", funcao: "função" },
    ],
    nota: "troque os nomes em slides_pitch/conteudo.js",
  },

  obrigado: {
    titulo: "Obrigado.",
    assinatura: "equipe vxwinners · Hackathon VX",
    url: "github.com/Igor-Roberto-Alves/vxwinners",
  },
};
