/* Códigos juntados e NCM trocado — o saneamento aberto, linha por linha.
 *
 * Lê artefatos/juncao_ncm.json (publicado em /frontend/dados/), gerado por
 * scripts/21_juncao_ncm.py a partir do plano de junção, do saneado e da base do
 * ERP. Duas listas completas, cada uma com o antes e o depois:
 *
 *   grupos        1.991 grupos de identidade. Em cada um, o código que FICA e os
 *                 que SAEM (bloqueados, apontando para o que fica), com saldo,
 *                 capital, centros e as divergências que a junção expõe
 *   ncm_trocado   NCM alterado item a item, separado pelo que a mudança significa:
 *                   trocado      dígitos diferentes — muda a tributação
 *                   preenchido   entrou vazio, derivado da classe PDM
 *                   reformatado  mesmos dígitos, só a pontuação
 *
 * Antes desta ligação a tela mostrava sete grupos escritos à mão dentro do
 * plataforma.html, com confiança inventada por grupo ("97%", "58%"), enquanto o
 * Radar dizia "1.991 grupos" e "1.104 NCM corrigidos" sem que houvesse onde
 * abrir nenhum dos dois. Aqui não há número que não venha do arquivo: a
 * confiança por grupo saiu, porque o pipeline não produz uma, e no lugar dela
 * aparece a precisão da junção medida no gabarito, que vale para o conjunto.
 *
 * As decisões ficam em localStorage e saem em .jsonl pelo botão "Exportar
 * decisões", uma linha por grupo revisado.
 */
(function () {
  "use strict";

  const ARQ = "frontend/dados/juncao_ncm.json";
  const ALT = "http://127.0.0.1:8000/frontend/dados/juncao_ncm.json";
  const CHAVE = "mro-juncao-decisoes";
  const POR_PAGINA_G = 25;
  const POR_PAGINA_N = 50;

  const ROTULO_TIPO = {
    trocado: "trocado", preenchido: "preenchido", reformatado: "reformatado",
  };
  const CLASSE_TIPO = {
    trocado: "b-err", preenchido: "b-warn", reformatado: "b-gray",
  };

  let dados = null;
  let aba = "grupos";
  let pagG = 1, pagN = 1;
  let atual = 0;              // índice do grupo aberto, na lista já filtrada
  let fica = {};              // override local de qual código fica, por chave
  let decisoes = {};

  const $ = (s) => document.querySelector(s);
  const el = (tag, attrs, ...filhos) => {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === "class") n.className = v;
      else if (k === "html") n.innerHTML = v;
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
      else if (v !== null && v !== undefined && v !== false) n.setAttribute(k, v);
    }
    for (const f of filhos.flat()) if (f !== null && f !== undefined) n.append(f);
    return n;
  };
  const inteiro = (v) => (v || 0).toLocaleString("pt-BR");
  const brl = (v) => "R$ " + (v || 0).toLocaleString("pt-BR",
    { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const brlCurto = (v) => (v >= 1e6
    ? "R$ " + (v / 1e6).toFixed(2).replace(".", ",") + " mi"
    : v >= 1e3 ? "R$ " + (v / 1e3).toFixed(0) + " mil" : brl(v));
  const qtd = (v) => (v || 0).toLocaleString("pt-BR", { maximumFractionDigits: 2 });
  const digitos = (s) => String(s || "").replace(/\D/g, "");
  const vazio = (v) => (v ? v : el("span", { class: "faint" }, "(vazio)"));

  /* O antes e o depois lado a lado, do jeito que já existe no painel de
   * evidências: o valor antigo riscado em vermelho, o novo em verde. */
  function troca(de, para) {
    if (!para || (de || "") === para) return el("span", { class: "mono" }, de || para || "");
    return el("span", { class: "troca" },
      de ? el("span", { class: "de" }, de) : el("span", { class: "faint" }, "(vazio)"),
      el("span", { class: "seta" }, "→"),
      el("span", { class: "para" }, para));
  }

  /* ------------------------------------------------------------- decisões */
  function carregaDecisoes() {
    try { decisoes = JSON.parse(localStorage.getItem(CHAVE) || "{}"); }
    catch (e) { decisoes = {}; }
  }
  function grava(g, tipo) {
    decisoes[g.chave] = {
      chave: g.chave, id_pdm: g.id_pdm,
      fica: fica[g.chave] || g.fica,
      fica_do_plano: g.fica,
      saem: g.saem, decisao: tipo,
      nota: ($("#jn-d-nota") && $("#jn-d-nota").value) || "",
      capital_liberado: g.capital_liberado,
      usuario: ($("#usuario") && $("#usuario").value.split("|")[0]) || "anonimo",
      quando: new Date().toISOString(),
      origem: "juncao_ncm",
    };
    try { localStorage.setItem(CHAVE, JSON.stringify(decisoes)); } catch (e) {}
  }

  /* ---------------------------------------------------------------- KPIs */
  function cartao(rotulo, valor, sub, dica, cor) {
    return el("div", { class: "card kpi", "data-tt": `${rotulo}|${sub}|${dica}` },
      el("div", { class: "l" }, rotulo,
        el("span", { class: "src-tag src-med", style: "margin-left:6px" }, "medido")),
      el("div", { class: "v", style: cor ? "color:" + cor : null }, valor),
      el("div", { class: "s" }, sub));
  }

  function pintaKpis() {
    const r = dados.resumo, n = r.ncm;
    const prec = r.precisao_juncao;
    $("#jn-kpis").replaceChildren(
      cartao("Grupos de códigos juntados", inteiro(r.grupos),
        `${inteiro(r.codigos_que_saem)} códigos saem · ${inteiro(r.saem_com_saldo)} com saldo`,
        "fonte: " + dados.fonte.juncao),
      cartao("Capital liberado", brlCurto(r.capital_liberado),
        "estoque dos códigos que saem, somado",
        "fonte: " + dados.fonte.capital),
      cartao("NCM trocado", inteiro(n.trocado),
        `${inteiro(n.preenchido)} preenchidos · ${inteiro(n.reformatado)} reformatados`,
        "fonte: " + dados.fonte.saneado, "var(--warn)"),
      prec
        ? cartao("Precisão da junção", prec.valor, prec.detalhe, "fonte: " + prec.origem)
        : cartao("Precisão da junção", "—", "gere o Radar para medir no gabarito",
          "scripts/20_radar.py"));

    const g = $("#jn-gerado");
    if (g) g.textContent = "· dados de " + (dados.gerado_em || "").replace("T", " ");
    const c = document.querySelector('.side-item[data-nav="clusters"] .count');
    if (c) c.textContent = inteiro(r.grupos);
    const abas = $("#jn-abas");
    if (abas) {
      abas.querySelector('[data-aba="grupos"]').textContent =
        `Códigos juntados · ${inteiro(r.grupos)} grupos`;
      abas.querySelector('[data-aba="ncm"]').textContent =
        `NCM trocado · ${inteiro(n.trocado)}`;
    }
  }

  /* -------------------------------------------------------------- grupos */
  function filtraGrupos() {
    const q = (($("#jn-g-busca") && $("#jn-g-busca").value) || "").trim().toUpperCase();
    const f = ($("#jn-g-filtro") && $("#jn-g-filtro").value) || "";
    const ordem = ($("#jn-g-ordem") && $("#jn-g-ordem").value) || "capital";
    let lista = dados.grupos.filter((g) => {
      if (f === "ncm" && !g.ncm_divergente) return false;
      if (f === "trocas" && !g.ncm_trocas) return false;
      if (f === "unidade" && !g.unidade_divergente) return false;
      if (f === "saldo" && !g.saem_com_saldo) return false;
      if (f === "llm" && !g.depende_de_llm) return false;
      if (f === "decididos" && !decisoes[g.chave]) return false;
      if (!q) return true;
      return g.chave.toUpperCase().includes(q) ||
        g.fica.includes(q) || (g.saem || []).some((c) => c.includes(q)) ||
        (g.descricao_pdm || "").toUpperCase().includes(q);
    });
    if (ordem === "codigos") lista = lista.slice().sort((a, b) => b.n - a.n ||
      b.capital_liberado - a.capital_liberado);
    else if (ordem === "saldo") lista = lista.slice().sort((a, b) =>
      b.saem_com_saldo - a.saem_com_saldo || b.capital_liberado - a.capital_liberado);
    return lista;
  }

  /* Rótulos curtos, com a frase inteira no title: a coluna precisa caber ao lado
   * de código que fica, códigos que saem, saldo e capital sem empurrar nada para
   * fora da tela. */
  function sinais(g) {
    const s = [];
    const b = (classe, texto, dica) =>
      s.push(el("span", { class: "badge " + classe, title: dica }, texto));
    if (g.ncm_trocas) b("b-err", `NCM alterado ×${g.ncm_trocas}`,
      `${g.ncm_trocas} código(s) deste grupo tiveram o NCM alterado pelo saneamento`);
    if (g.ncm_divergente) b("b-warn", "NCM ≠",
      "o mesmo item está com NCM diferente entre os códigos");
    if (g.unidade_divergente) b("b-warn", "unidade ≠",
      "unidades diferentes entre os códigos: o saldo só soma com fator de conversão");
    if (g.saem_com_saldo) b("", `${g.saem_com_saldo} c/ saldo`,
      `${g.saem_com_saldo} código(s) que saem têm estoque`);
    if (g.depende_de_llm) b("b-ia", "LLM",
      "a chave de identidade usou valor decidido por LLM" +
      (g.llm_na_chave && g.llm_na_chave.length ? ": " + g.llm_na_chave.join(", ") : ""));
    return s;
  }

  function tabelaGrupos(lista) {
    const paginas = Math.max(1, Math.ceil(lista.length / POR_PAGINA_G));
    pagG = Math.min(Math.max(1, pagG), paginas);
    const fatia = lista.slice((pagG - 1) * POR_PAGINA_G, pagG * POR_PAGINA_G);

    const thead = el("thead", {}, el("tr", {},
      el("th", {}, "GRUPO DE IDENTIDADE"),
      el("th", { class: "num", title: "quantos códigos no grupo" }, "CÓD."),
      el("th", { title: "código que permanece ativo" }, "FICA"),
      el("th", { title: "códigos bloqueados, que passam a apontar para o que fica" }, "SAEM"),
      el("th", { class: "num", title: "saldo dos códigos do grupo, somado" }, "SALDO"),
      el("th", { class: "num", title: "estoque dos códigos que saem" }, "CAPITAL"),
      el("th", {}, "O QUE DIVERGE"),
      el("th", {}, "REVISÃO")));

    const tbody = el("tbody", {}, fatia.map((g) => {
      const d = decisoes[g.chave];
      const i = lista.indexOf(g);
      return el("tr", {
        class: i === atual ? "sel" : "", style: "cursor:pointer",
        onclick: () => { atual = i; desenhaGrupos(); abreDetalhe(); },
      },
        // a chave pode ser longa (classe com sete atributos de identidade): na
        // lista vai o começo, com a chave inteira no título e no detalhe
        el("td", { class: "wrap", style: "max-width:300px", title: g.chave },
          el("div", { style: "font-size:12px" },
            g.titulo.length > 72 ? g.titulo.slice(0, 72) + "…" : g.titulo),
          el("div", { class: "mono faint", style: "font-size:10.5px" },
            g.id_pdm + " · " + g.centros.map((c) => c.split(" - ")[0]).join(", "))),
        el("td", { class: "num" }, String(g.n)),
        el("td", {}, el("span", { class: "mono fica" }, g.fica)),
        el("td", { class: "wrap" }, el("span", { class: "mono saem", style: "font-size:11.5px" },
          g.saem.join(" "))),
        el("td", { class: "num" }, qtd(g.estoque_consolidado) + " " + (g.unidade || "")),
        el("td", { class: "num" }, brl(g.capital_liberado)),
        el("td", { class: "wrap" }, sinais(g)),
        el("td", {}, d
          ? el("span", { class: "badge b-green" }, d.decisao)
          : el("span", { class: "badge b-gray" }, "aberto")));
    }));

    $("#jn-g-table").replaceChildren(thead, tbody);
    $("#jn-g-conta").textContent =
      `${inteiro(lista.length)} grupo(s) · página ${pagG} de ${paginas}`;
    $("#jn-g-pager").replaceChildren(
      el("button", { class: "btn sm", onclick: () => { pagG--; desenhaGrupos(); } }, "‹"),
      el("span", { style: "font-size:12px" }, `${pagG} / ${paginas}`),
      el("button", { class: "btn sm", onclick: () => { pagG++; desenhaGrupos(); } }, "›"),
      el("span", { class: "faint", style: "margin-left:auto" },
        `${inteiro(Object.keys(decisoes).length)} revisão(ões) nesta sessão`));
  }

  function desenhaGrupos() {
    const lista = filtraGrupos();
    const r = dados.resumo;
    $("#jn-g-sub").textContent =
      `${inteiro(r.grupos)} grupos · ${inteiro(r.codigos_que_saem)} códigos a bloquear ` +
      `em ${inteiro(r.codigos_no_plano)} do plano`;
    tabelaGrupos(lista);
    return lista;
  }

  /* ------------------------------------------------------- detalhe do grupo */
  function porQue(g, cod) {
    const partes = g.chave.split("|");
    const avisos = [];
    if (g.unidade_divergente) avisos.push(
      "as unidades divergem entre os códigos: o saldo só pode ser somado depois do " +
      "fator de conversão (uma caixa não é uma peça)");
    if (g.ncm_divergente) avisos.push(
      "o mesmo item está com NCM diferente entre os códigos — a junção expõe a " +
      "divergência fiscal que já existia na base");
    if (g.saem_com_saldo) avisos.push(
      `${g.saem_com_saldo} código(s) que saem têm saldo em estoque: bloquear não ` +
      "move material, só impede cadastro novo");
    if (g.depende_de_llm) avisos.push(
      "a chave usou valor decidido por LLM" +
      (g.llm_na_chave && g.llm_na_chave.length
        ? ` (${g.llm_na_chave.join(", ")})` : "") + ": confira antes de unificar");

    return el("div", { class: "callout " + (avisos.length ? "warn" : "ok") },
      el("div", { style: "font-size:12.5px" },
        el("b", { style: "font-weight:500" },
          `Os ${g.n} códigos têm a mesma chave de identidade do PDM.`),
        " ",
        el("span", { class: "mono", style: "font-size:11.5px" }, partes.join(" · ")),
        el("div", { style: "margin-top:6px" },
          "O plano mantém o ", el("span", { class: "mono fica" }, g.fica),
          " e bloqueia ", el("span", { class: "mono saem" }, g.saem.join(" ")),
          ". Cada bloqueado passa a apontar para o que fica — nenhum código é apagado."),
        cod.codigo !== g.fica
          ? el("div", { style: "margin-top:6px;color:var(--warn)" },
            "Você escolheu manter o ", el("span", { class: "mono" }, cod.codigo),
            " em vez do ", el("span", { class: "mono" }, g.fica),
            " do plano: a troca vai na decisão exportada.")
          : null,
        avisos.length
          ? el("ul", { style: "margin:8px 0 0 18px" },
            avisos.map((a) => el("li", { style: "margin:2px 0" }, a)))
          : null));
  }

  /* As linhas da comparação. `valor` devolve o que a célula mostra e `norma` o
   * que define "igual": sem isso, 8431.4929 e 8431.49.29 apareciam como
   * divergência de NCM quando é o mesmo código fiscal escrito de dois jeitos. */
  const LINHAS = [
    { rotulo: "Descrição (como está hoje)", valor: (c) => el("span",
      { class: "mono", style: "font-size:11px" }, c.descricao || ""), nunca_diff: true },
    { rotulo: "Unidade", valor: (c) => troca(c.unidade_de, c.unidade_para),
      norma: (c) => c.unidade_para || c.unidade_de || "" },
    { rotulo: "NCM", valor: (c) => troca(c.ncm_de, c.ncm_para),
      norma: (c) => digitos(c.ncm_para || c.ncm_de) },
    { rotulo: "Motivo do NCM", valor: (c) => el("span", { class: "faint",
      style: "font-size:11px" }, c.ncm_motivo || "—"), nunca_diff: true },
    { rotulo: "Grupo de mercadoria", valor: (c) => el("span", { class: "mono" },
      c.grupo_mercadoria || ""), norma: (c) => c.grupo_mercadoria || "" },
    { rotulo: "Fabricante (campo)", valor: (c) => vazio(c.fabricante),
      norma: (c) => c.fabricante || "" },
    { rotulo: "Referência (campo)", valor: (c) => vazio(c.referencia),
      norma: (c) => c.referencia || "" },
    { rotulo: "Centro", valor: (c) => el("span", { class: "mono",
      style: "font-size:11.5px" }, c.centro || ""), nunca_diff: true },
    { rotulo: "Status", valor: (c) => el("span", {
      class: "badge " + (c.status === "ATIVO" ? "b-green"
        : c.status === "BLOQUEADO" ? "b-err" : "b-warn") }, c.status || "—"),
      norma: (c) => c.status || "" },
    { rotulo: "Estoque", valor: (c) => el("span", { class: "mono" },
      qtd(c.estoque) + " " + (c.unidade_para || c.unidade_de || "")), nunca_diff: true },
    { rotulo: "Preço médio", valor: (c) => el("span", { class: "mono" }, brl(c.preco)),
      nunca_diff: true },
    { rotulo: "Capital parado", valor: (c) => el("span", { class: "mono" }, brl(c.capital)),
      nunca_diff: true },
  ];

  /* As linhas originais, uma por código, na ordem das colunas da base_materiais.
   * A comparação campo a campo (abaixo) serve para achar a divergência; esta
   * tabela serve para reconhecer o item — é o registro como o ERP tem hoje, que
   * é o que o almoxarifado e o tributário conferem. */
  function linhasOriginais(g, escolhido) {
    const ref = g.codigos.find((c) => c.codigo === escolhido) || g.codigos[0];
    const difere = (c, campo) => (c[campo] || "") !== (ref[campo] || "");
    const colunas = [
      ["CODIGO_MATERIAL", (c) => el("span", { class: "mono " + (c.acao === "mantem" ? "fica" : "saem") }, c.codigo)],
      ["DECISÃO", (c) => c.acao === "mantem"
        ? el("span", { class: "badge b-green" }, "FICA")
        : el("span", { class: "badge b-err", title: "bloqueado, apontando para " + escolhido },
          "SAI → " + escolhido)],
      ["DESCRICAO_LONGA", (c) => el("span", { class: "mono", style: "font-size:10.5px" },
        c.descricao || c.curta || "")],
      ["UN", (c) => troca(c.unidade_de, c.unidade_para), (c) => difere(c, "unidade_de")],
      ["NCM", (c) => troca(c.ncm_de, c.ncm_para),
        (c) => digitos(c.ncm_de) !== digitos(ref.ncm_de)],
      ["STATUS", (c) => el("span", {
        class: "badge " + (c.status === "ATIVO" ? "b-green"
          : c.status === "BLOQUEADO" ? "b-err" : "b-warn"),
      }, c.status || "—")],
      ["ESTOQUE", (c) => el("span", { class: "mono" },
        qtd(c.estoque) + " " + (c.unidade_para || c.unidade_de || "")), null, "num"],
      ["CAPITAL", (c) => el("span", { class: "mono" }, brl(c.capital)), null, "num"],
      ["CENTRO", (c) => el("span", { class: "mono", style: "font-size:11.5px" }, c.centro || "")],
      ["GRUPO", (c) => el("span", { class: "mono" }, c.grupo_mercadoria || ""),
        (c) => difere(c, "grupo_mercadoria")],
      ["FABRICANTE", (c) => vazio(c.fabricante), (c) => difere(c, "fabricante")],
      ["REFERENCIA", (c) => vazio(c.referencia), (c) => difere(c, "referencia")],
      ["PRECO_MEDIO", (c) => el("span", { class: "mono" }, brl(c.preco)), null, "num"],
      ["CRIADO", (c) => el("span", { class: "mono faint", style: "font-size:11px" },
        c.criado || "—")],
      ["ÚLT. MOV.", (c) => el("span", { class: "mono faint", style: "font-size:11px" },
        c.movimentado || "—")],
    ];

    const thead = el("thead", {}, el("tr", {}, colunas.map(([rotulo, , , classe]) =>
      el("th", { class: classe === "num" ? "num" : "" }, rotulo))));
    const tbody = el("tbody", {}, g.codigos.map((c) => el("tr", {
      class: c.acao === "mantem" ? "sel" : "",
    }, colunas.map(([rotulo, valor, divergiu, classe]) => el("td", {
      class: [classe === "num" ? "num" : "",
        rotulo === "DESCRICAO_LONGA" ? "wrap" : "",
        divergiu && divergiu(c) ? "diff" : ""].filter(Boolean).join(" "),
      style: rotulo === "DESCRICAO_LONGA" ? "max-width:300px" : null,
    }, valor(c))))));

    $("#jn-d-linhas").replaceChildren(thead, tbody);
    const sub = $("#jn-d-linhas-sub");
    if (sub) sub.textContent =
      ` · ${g.n} linhas · ${brl(g.capital_total)} somando o grupo inteiro`;
  }

  function abreDetalhe() {
    const lista = filtraGrupos();
    if (!lista.length) {
      $("#jn-d-titulo").textContent = "Nada com esse filtro";
      $("#jn-d-linhas").replaceChildren();
      $("#jn-d-cmp").replaceChildren();
      $("#jn-d-por-que").replaceChildren();
      $("#jn-d-imp").replaceChildren();
      return;
    }
    atual = Math.min(Math.max(0, atual), lista.length - 1);
    const g = lista[atual];
    const escolhido = fica[g.chave] || g.fica;
    const cod = g.codigos.find((c) => c.codigo === escolhido) || g.codigos[0];

    $("#jn-d-titulo").textContent = g.titulo;
    $("#jn-d-sub").textContent =
      `${g.n} códigos · ${g.id_pdm} · ${g.centros.length} centro(s) · ` +
      `${brl(g.capital_liberado)} liberados`;
    $("#jn-d-chave").textContent = g.chave;
    $("#jn-d-por-que").replaceChildren(porQue(g, cod));
    linhasOriginais(g, escolhido);

    // cabeçalho: o rádio deixa trocar qual código fica, e a troca vai na decisão
    const thead = el("thead", {}, el("tr", {},
      el("th", {}, ""),
      g.codigos.map((c) => {
        const ehEscolhido = c.codigo === escolhido;
        return el("th", { class: ehEscolhido ? "keep" : "" },
          el("label", { style: "display:flex;gap:6px;align-items:center;cursor:pointer" },
            el("input", {
              type: "radio", name: "jn-fica", checked: ehEscolhido,
              onchange: () => { fica[g.chave] = c.codigo; abreDetalhe(); },
            }),
            el("span", { class: "mono" }, c.codigo)),
          el("div", { style: "margin-top:4px" },
            ehEscolhido
              ? el("span", { class: "badge b-green" }, "FICA")
              : el("span", { class: "badge b-err" }, "SAI → " + escolhido)));
      })));

    const tbody = el("tbody", {}, LINHAS.map((L) => {
      const ref = L.norma ? L.norma(cod) : null;
      return el("tr", {},
        el("td", {}, L.rotulo),
        g.codigos.map((c) => {
          const diff = L.norma && !L.nunca_diff && L.norma(c) !== ref;
          return el("td", { class: diff ? "diff" : "same" }, L.valor(c));
        }));
    }));
    $("#jn-d-cmp").replaceChildren(thead, tbody);

    const liberado = g.codigos.filter((c) => c.codigo !== escolhido)
      .reduce((a, c) => a + c.capital, 0);
    const saldo = g.codigos.reduce((a, c) => a + c.estoque, 0);
    $("#jn-d-imp").replaceChildren(...[
      ["Código que fica", escolhido],
      ["Saldo somado", qtd(saldo) + " " + (cod.unidade_para || cod.unidade_de || "")],
      ["Capital liberado", brl(liberado)],
      ["Códigos bloqueados", String(g.n - 1)],
    ].map(([a, b]) => el("div", { class: "fx", style: "padding:10px 12px" },
      el("div", { class: "faint", style: "font-size:11px" }, a),
      el("div", { class: "mono", style: "font-size:14px;margin-top:2px" }, b))));

    const nota = $("#jn-d-nota");
    if (nota) nota.value = (decisoes[g.chave] || {}).nota || "";
  }

  function decide(tipo) {
    const lista = filtraGrupos();
    if (!lista.length) return;
    const g = lista[atual];
    if (tipo !== "pular") {
      grava(g, tipo);
      if (window.toast) toast(`${tipo} · ${g.fica} (${g.saem.length} bloqueados)`);
    }
    atual = (atual + 1) % lista.length;
    desenhaGrupos();
    abreDetalhe();
    $("#jn-detalhe").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  /* ----------------------------------------------------------------- NCM */
  function tilesNcm() {
    const n = dados.resumo.ncm;
    const tile = (tipo, rotulo, valor, sub) => el("div", {
      class: "fx", style: "padding:10px 12px;cursor:" + (tipo ? "pointer" : "default"),
      onclick: tipo ? () => {
        $("#jn-n-tipo").value = $("#jn-n-tipo").value === tipo ? "" : tipo;
        pagN = 1; desenhaNcm();
      } : null,
    },
      el("div", { class: "faint", style: "font-size:11px" }, rotulo),
      el("div", { class: "mono", style: "font-size:18px;margin-top:2px" }, inteiro(valor)),
      el("div", { class: "faint", style: "font-size:11px;margin-top:2px" }, sub));

    $("#jn-n-tipos").replaceChildren(
      tile("trocado", "trocado · muda a tributação", n.trocado,
        brlCurto(n.capital_trocado) + " em estoque"),
      tile("preenchido", "preenchido · entrou vazio", n.preenchido,
        "derivado da classe PDM"),
      tile("reformatado", "reformatado · só a pontuação", n.reformatado,
        `${inteiro(n.reformatado_publicado)} nesta tela`),
      tile(null, "continua sem NCM", n.sem_ncm,
        "a classe tem NCM condicional: vai para a fila"));

    $("#jn-n-sub").textContent =
      `${inteiro(n.trocado + n.preenchido + n.reformatado)} de ${inteiro(dados.resumo.itens_na_base)} ` +
      `itens tiveram o NCM alterado · ${inteiro(n.inalterado)} ficaram como estavam`;
    $("#jn-n-nota").textContent =
      "Trocado muda a tributação do item e, pela regra do projeto, nenhuma alteração " +
      "de NCM chega ao ERP sem aprovação do tributário. Reformatado é só pontuação " +
      `(${inteiro(n.reformatado)} casos; ${inteiro(n.reformatado_publicado)} publicados ` +
      "aqui, os de maior capital). " +
      `${inteiro(n.trocado_em_grupo)} dos trocados estão em grupo de junção.`;
  }

  function filtraNcm() {
    const q = (($("#jn-n-busca") && $("#jn-n-busca").value) || "").trim().toUpperCase();
    const t = ($("#jn-n-tipo") && $("#jn-n-tipo").value) || "";
    const ordem = ($("#jn-n-ordem") && $("#jn-n-ordem").value) || "capital";
    let lista = dados.ncm_trocado.filter((x) => {
      if (t && x.tipo !== t) return false;
      if (!q) return true;
      return x.codigo.includes(q) || (x.de || "").includes(q) || (x.para || "").includes(q) ||
        (x.id_pdm || "").includes(q) || (x.motivo || "").toUpperCase().includes(q) ||
        (x.descricao || "").toUpperCase().includes(q);
    });
    if (ordem === "codigo") lista = lista.slice().sort((a, b) => a.codigo.localeCompare(b.codigo));
    return lista;
  }

  function desenhaNcm() {
    const lista = filtraNcm();
    const paginas = Math.max(1, Math.ceil(lista.length / POR_PAGINA_N));
    pagN = Math.min(Math.max(1, pagN), paginas);
    const fatia = lista.slice((pagN - 1) * POR_PAGINA_N, pagN * POR_PAGINA_N);

    const thead = el("thead", {}, el("tr", {},
      el("th", {}, "CÓDIGO"), el("th", {}, "CLASSE"), el("th", {}, "DESCRIÇÃO"),
      el("th", {}, "NCM: DE → PARA"), el("th", {}, "TIPO"), el("th", {}, "MOTIVO"),
      el("th", {}, "CENTRO"), el("th", { class: "num" }, "CAPITAL"), el("th", {}, "")));

    const tbody = el("tbody", {}, fatia.map((x) => el("tr", {},
      el("td", { class: "mono" }, x.codigo),
      el("td", { class: "mono faint" }, x.id_pdm || ""),
      el("td", { class: "wrap", style: "font-size:11.5px;max-width:260px" }, x.descricao || ""),
      el("td", {}, troca(x.de, x.para)),
      el("td", {}, el("span", { class: "badge " + (CLASSE_TIPO[x.tipo] || "") },
        ROTULO_TIPO[x.tipo] || x.tipo)),
      el("td", { class: "wrap faint", style: "font-size:11.5px;max-width:230px" },
        x.motivo || "—"),
      el("td", { class: "mono", style: "font-size:11.5px" },
        (x.centro || "").split(" - ")[0]),
      el("td", { class: "num" }, brl(x.capital)),
      el("td", {}, x.grupo_juncao
        ? el("button", {
          class: "btn sm ghost",
          title: "abre o grupo de junção deste código",
          onclick: () => abreGrupoPorChave(x.grupo_juncao),
        }, "ver grupo")
        : null))));

    $("#jn-n-table").replaceChildren(thead, tbody);
    $("#jn-n-conta").textContent =
      `${inteiro(lista.length)} linha(s) · página ${pagN} de ${paginas}`;
    $("#jn-n-pager").replaceChildren(
      el("button", { class: "btn sm", onclick: () => { pagN--; desenhaNcm(); } }, "‹"),
      el("span", { style: "font-size:12px" }, `${pagN} / ${paginas}`),
      el("button", { class: "btn sm", onclick: () => { pagN++; desenhaNcm(); } }, "›"));
    const sel = $("#jn-n-tipo");
    if (sel) [...$("#jn-n-tipos").children].forEach((t, i) =>
      t.classList.toggle("on", ["trocado", "preenchido", "reformatado"][i] === sel.value));
  }

  function abreGrupoPorChave(chave) {
    // o grupo pode estar fora do filtro corrente: limpa o filtro antes de abrir,
    // senão o "ver grupo" levava para um índice que não existe na lista filtrada
    $("#jn-g-filtro").value = "";
    $("#jn-g-busca").value = "";
    const lista = filtraGrupos();
    const i = lista.findIndex((g) => g.chave === chave);
    if (i < 0) { if (window.toast) toast("Esse grupo não está na lista publicada."); return; }
    atual = i;
    pagG = Math.floor(i / POR_PAGINA_G) + 1;
    mostraAba("grupos");
    desenhaGrupos();
    abreDetalhe();
    $("#jn-detalhe").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  /* --------------------------------------------------------------- abas */
  function mostraAba(qual) {
    aba = qual;
    $("#jn-aba-grupos").style.display = qual === "grupos" ? "" : "none";
    $("#jn-aba-ncm").style.display = qual === "ncm" ? "" : "none";
    $("#jn-abas").querySelectorAll(".seg-btn").forEach((b) =>
      b.classList.toggle("on", b.dataset.aba === qual));
    if (qual === "ncm") desenhaNcm();
  }

  /* --------------------------------------------------------------- saída */
  function exporta() {
    const linhas = Object.values(decisoes).map((d) => JSON.stringify(d)).join("\n");
    if (!linhas) { if (window.toast) toast("Nenhuma revisão para exportar."); return; }
    const url = URL.createObjectURL(new Blob([linhas + "\n"], { type: "application/x-ndjson" }));
    const a = el("a", { href: url, download: "juncao_decisoes.jsonl" });
    document.body.append(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
    if (window.toast) toast(`${Object.keys(decisoes).length} revisões exportadas.`);
  }

  function limpa() {
    if (!confirm("Apagar as revisões desta sessão?")) return;
    decisoes = {}; fica = {};
    try { localStorage.removeItem(CHAVE); } catch (e) {}
    desenhaGrupos(); abreDetalhe();
  }

  /* --------------------------------------------------------- carregamento */
  function falhou() {
    $("#jn-kpis").replaceChildren(el("div", {
      class: "card", style: "grid-column:1/-1;padding:16px;line-height:1.7",
    },
      el("b", {}, "Não achei os dados da junção."),
      el("div", { class: "faint", style: "margin-top:6px" }, "Gere com"),
      el("div", { class: "pdm-preview", style: "margin-top:8px" },
        "uv run --no-project --with pandas --with openpyxl python scripts/21_juncao_ncm.py"),
      el("div", { class: "faint", style: "margin-top:8px" },
        "e abra a plataforma pelo servidor (./rodar.sh), não pelo arquivo: o navegador " +
        "bloqueia leitura de arquivo local.")));
  }

  let carregando = false;
  async function carrega() {
    if (dados || carregando) return;
    carregando = true;
    $("#jn-g-sub").textContent = "carregando…";
    for (const url of [ARQ, ALT]) {
      try {
        const r = await fetch(url, { cache: "no-store" });
        if (!r.ok) continue;
        dados = await r.json();
        break;
      } catch (e) { /* tenta a próxima */ }
    }
    carregando = false;
    if (!dados) { falhou(); return; }
    carregaDecisoes();
    pintaKpis();
    desenhaGrupos();
    abreDetalhe();
    if (aba === "ncm") desenhaNcm();
    else tilesNcm();
  }

  function liga() {
    const pagina = $("#page-clusters");
    if (!pagina) return;

    for (const id of ["#jn-g-busca", "#jn-g-filtro", "#jn-g-ordem"]) {
      const n = $(id);
      if (n) n.addEventListener(n.tagName === "INPUT" ? "input" : "change",
        () => { pagG = 1; atual = 0; desenhaGrupos(); abreDetalhe(); });
    }
    for (const id of ["#jn-n-busca", "#jn-n-tipo", "#jn-n-ordem"]) {
      const n = $(id);
      if (n) n.addEventListener(n.tagName === "INPUT" ? "input" : "change",
        () => { pagN = 1; desenhaNcm(); });
    }
    $("#jn-abas").addEventListener("click", (e) => {
      const b = e.target.closest("[data-aba]");
      if (b) mostraAba(b.dataset.aba);
    });
    $("#jn-detalhe").addEventListener("click", (e) => {
      const b = e.target.closest("[data-jn-dec]");
      if (b) decide(b.dataset.jnDec);
    });
    const ex = $("#jn-exportar"); if (ex) ex.addEventListener("click", exporta);
    const lp = $("#jn-limpar"); if (lp) lp.addEventListener("click", limpa);

    // o arquivo tem 4 MB: só busca quando a página é aberta de fato, para não
    // pesar no carregamento de quem entrou para usar outra tela
    if (pagina.classList.contains("active")) carrega();
    new MutationObserver(() => {
      if (pagina.classList.contains("active")) carrega();
    }).observe(pagina, { attributes: true, attributeFilter: ["class"] });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", liga);
  else liga();
})();
