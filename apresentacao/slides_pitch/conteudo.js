/* =====================================================================
   CONTEUDO DO DECK — edite aqui os textos. O index.html monta os slides
   a partir deste objeto; nenhum numero deve ser alterado sem conferir a
   fonte.
   ===================================================================== */
window.CONTEUDO = {
  capa: {
    titulo: "Prumo",
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
    // linha 1: pipeline oficial (gabaritos) · linha 2: benchmark de preenchimento
    medidores: [
      { campo: "Classe", valor: "90,8%", pct: 90.8, nota: "acerto · 218 de 240 itens" },
      { campo: "Atributos", valor: "97,5%", pct: 97.5, nota: "precisão · IC 96–98% · 1.131 rótulos" },
      { campo: "Junção", valor: "98,5%", pct: 98.5, nota: "precisão · recall 97,0%" },
      { campo: "NCM", valor: "91,1%", pct: 91.1, nota: "top-1 · 99,0% top-3" },
      { campo: "Fabricante", valor: "84,3%", pct: 84.3, nota: "acerto exato" },
      { campo: "Referência", valor: "84,4%", pct: 84.4, nota: "part number · acerto exato" },
    ],
    faixa:
      "Conjunto-ouro com dupla anotação: precisão 96,2% [94–98%] · 24.575 campos preenchidos por US$ 21 · Fable 5 (modelo mais caro) testado e não lidera nenhum campo",
  },

  dinheiro: {
    etiqueta: "04 · Dinheiro na mesa",
    titulo: "R$ 30,24 mi consolidáveis no estoque",
    // valores em R$ milhões — barra horizontal, uma matiz lavanda
    // fonte: artefatos/radar.json (hero: consolidavel, fila, consolidado)
    barras: [
      {
        rotulo: "Capital consolidável",
        nota: "15,1% dos R$ 200,87 mi · 2.676 códigos em 1.991 grupos",
        valor: 30.24,
        texto: "R$ 30,24 mi",
      },
      {
        rotulo: "Na fila de intervenção",
        nota: "3.482 itens · 1.478 resolvem com um clique",
        valor: 10.84,
        texto: "R$ 10,84 mi",
      },
      {
        rotulo: "Já consolidado",
        nota: "o plano está pronto; nenhuma unificação executada no ERP",
        valor: 0,
        texto: "R$ 0,00",
      },
    ],
    destaque: {
      titulo: "Identidade destravada",
      valor: "R$ 101,2 mi",
      nota: "estoque que ganhou chave de identidade e entra na comparação de duplicatas",
    },
    rodape:
      "Fonte: artefatos/radar.json · plano_juncao.csv · fila_intervencao.json — valores medidos na base do desafio, não projetados",
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
    membros: [
      { nome: "Igor Roberto Alves", funcao: "pipeline & avaliação" },
      { nome: "Letícia Aleixo", funcao: "interface & plataforma" },
      { nome: "Pedro Porto", funcao: "backend & integração" },
      { nome: "Richard Viana", funcao: "preenchimento & demo" },
    ],
  },

  obrigado: {
    titulo: "Obrigado.",
    assinatura: "equipe vxwinners · Hackathon VX",
    url: "github.com/Igor-Roberto-Alves/vxwinners",
  },
};
