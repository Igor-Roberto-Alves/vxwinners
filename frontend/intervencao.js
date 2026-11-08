/* Fila de intervenção humana — a tela onde o saneamento pede ajuda.
 *
 * Lê artefatos/fila_intervencao.json (publicado em /frontend/dados/), gerado por
 * scripts/19_fila_intervencao.py a partir da saída do pipeline. Cada campo vazio
 * chega classificado pela AÇÃO que ele pede, e não pelo erro que ele é:
 *
 *   um_clique   o valor está decidido (o texto trazia e a leitura perdeu, ou há
 *               candidato único/provável acima de 90%): confirmar e seguir
 *   escolher    dois ou mais candidatos plausíveis, com probabilidade e suporte
 *   sem_pista   o texto traz algo fora do padrão e nada se sustenta
 *   enriquecer  o texto não traz o dado: não é trabalho de leitura (fica à parte)
 *
 * A fila é ordenada por capital em risco (estoque × preço médio), então a hora
 * de uma pessoa vai primeiro para o código que custa mais caro.
 *
 * As decisões ficam em localStorage e saem em .jsonl pelo botão "Exportar
 * decisões", no formato que o pipeline consome de volta.
 */
(function () {
  "use strict";

  const FI_ARQ = "frontend/dados/fila_intervencao.json";
  const FI_ALT = "http://127.0.0.1:8000/frontend/dados/fila_intervencao.json";
  const FI_CHAVE = "mro-intervencao-decisoes";
  const FI_PAGINA = 20;

  const ROTULO_ACAO = {
    um_clique: "confirmar",
    escolher: "escolher",
    sem_pista: "sem pista",
    enriquecer: "fonte externa",
  };
  const CLASSE_ACAO = {
    um_clique: "b-green",
    escolher: "b-warn",
    sem_pista: "b-err",
    enriquecer: "",
  };

  let fila = null;
  let pagina = 1;
  let decisoes = {};

  const $ = (s) => document.querySelector(s);
  const el = (tag, attrs, ...filhos) => {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === "class") n.className = v;
      else if (k === "html") n.innerHTML = v;
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
      else if (v !== null && v !== undefined) n.setAttribute(k, v);
    }
    for (const f of filhos.flat()) if (f !== null && f !== undefined) n.append(f);
    return n;
  };
  const brl = (v) =>
    "R$ " + (v || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const inteiro = (v) => (v || 0).toLocaleString("pt-BR");
  const pct = (p) => Math.round(p * 100) + "%";
  // mesmos limiares do confCls() da plataforma: >=80 verde, >=60 amarelo, abaixo vermelho
  const classeConf = (p) => (p * 100 >= 80 ? "hi" : p * 100 >= 60 ? "md" : "lo");
  // O numero NAO e confianca: e a fatia da distribuicao de candidatos daquele
  // campo. Com um candidato unico da 100% por construcao. Quem mede acerto e o
  // teste retroativo por faixa, mostrado ao lado como nota. Sem isso, a primeira
  // versao desta tela exibia "100%" em 68 campos e "100%" inventado por mim em
  // outros 43 (os PERDIDO), tudo com a mesma cara de certeza.
  const pilulaConf = (p) =>
    el("span", {
      class: "conf-pill " + classeConf(p),
      title: pct(p) + " da distribuição de candidatos deste campo — não é taxa de acerto",
    }, el("i", {}), pct(p), el("span", { style: "opacity:.75;margin-left:4px" }, "dos cand."));

  function carregaDecisoes() {
    try { decisoes = JSON.parse(localStorage.getItem(FI_CHAVE) || "{}"); }
    catch (e) { decisoes = {}; }
  }
  function gravaDecisao(codigo, atributo, valor, tipo) {
    decisoes[codigo + "|" + atributo] = {
      codigo, atributo, valor, decisao: tipo,
      usuario: ($("#usuario") && $("#usuario").value.split("|")[0]) || "anonimo",
      quando: new Date().toISOString(),
      origem: "fila_intervencao",
    };
    try { localStorage.setItem(FI_CHAVE, JSON.stringify(decisoes)); } catch (e) {}
  }

  /* ----------------------------------------------------------- carregamento */
  async function carrega() {
    const alvo = $("#fi-lista");
    if (!alvo) return;
    alvo.replaceChildren(el("div", { class: "faint", style: "padding:16px" }, "Carregando a fila…"));
    for (const url of [FI_ARQ, FI_ALT]) {
      try {
        const r = await fetch(url, { cache: "no-store" });
        if (!r.ok) continue;
        fila = await r.json();
        break;
      } catch (e) { /* tenta a próxima */ }
    }
    if (!fila) {
      alvo.replaceChildren(
        el("div", { class: "card", style: "padding:16px;line-height:1.7" },
          el("b", {}, "Não achei a fila."),
          el("div", { class: "faint", style: "margin-top:6px" },
            "Gere com "),
          el("div", { class: "pdm-preview", style: "margin-top:8px" },
            "uv run --no-project --with pandas --with openpyxl python scripts/19_fila_intervencao.py"),
          el("div", { class: "faint", style: "margin-top:8px" },
            "e abra a plataforma pelo servidor (./rodar.sh), não pelo arquivo: " +
            "o navegador bloqueia leitura de arquivo local.")));
      return;
    }
    carregaDecisoes();
    pintaKpis();
    preencheClasses();
    render();
  }

  function pintaKpis() {
    const r = fila.resumo, a = r.campos_por_acao || {};
    const def = (id, v) => { const n = $(id); if (n) n.textContent = v; };
    def("#fi-k-itens", inteiro(r.itens_na_fila));
    def("#fi-k-itens-s", `${inteiro(r.itens_exportados)} nesta tela, os de maior capital`);
    def("#fi-k-clique", inteiro(a.um_clique || 0));
    def("#fi-k-clique-s", `valor já decidido — confirmar e seguir`);
    def("#fi-k-escolher", inteiro((a.escolher || 0) + (a.sem_pista || 0)));
    def("#fi-k-escolher-s", `${inteiro(a.escolher || 0)} com candidatos · ${inteiro(a.sem_pista || 0)} sem pista`);
    def("#fi-k-capital", brl(r.capital_na_fila));
    def("#fi-k-capital-s", `estoque × preço médio dos itens da fila`);
    const n = $("#n-intervencao");
    if (n) n.textContent = inteiro(r.itens_na_fila);
    const g = $("#fi-gerado");
    if (g) g.textContent = "gerado em " + (fila.gerado_em || "").replace("T", " ");
  }

  function preencheClasses() {
    const sel = $("#fi-classe");
    if (!sel) return;
    const classes = [...new Set(fila.itens.map((i) => i.id_pdm))].sort();
    for (const c of classes) sel.append(el("option", { value: c }, c));
  }

  /* ------------------------------------------------------------- filtragem */
  function ordena(lista) {
    const modo = ($("#fi-ordem") && $("#fi-ordem").value) || "acionavel";
    const copia = lista.slice();
    if (modo === "capital") return copia.sort((a, b) => b.capital - a.capital);
    if (modo === "campos") return copia.sort((a, b) =>
      (b.n_um_clique + b.n_escolher + b.n_sem_pista) - (a.n_um_clique + a.n_escolher + a.n_sem_pista)
      || b.capital - a.capital);
    // "acionavel" (padrao): quem tem campo de um clique primeiro, depois quem tem
    // candidato para escolher, e dentro de cada grupo o capital decide. Ordenar so
    // por capital enchia a primeira tela de 'sem pista', que e justo o que ninguem
    // consegue resolver sem consultar catalogo.
    const nivel = (i) => (i.n_um_clique ? 0 : i.n_escolher ? 1 : 2);
    return copia.sort((a, b) => nivel(a) - nivel(b) || b.capital - a.capital);
  }

  function filtrados() {
    const q = (($("#fi-busca") && $("#fi-busca").value) || "").trim().toUpperCase();
    const acao = ($("#fi-acao") && $("#fi-acao").value) || "";
    const classe = ($("#fi-classe") && $("#fi-classe").value) || "";
    const pendentes = $("#fi-pendentes") && $("#fi-pendentes").checked;
    return ordena(fila.itens).filter((i) => {
      if (classe && i.id_pdm !== classe) return false;
      if (q && !(i.codigo.includes(q) || (i.texto || "").toUpperCase().includes(q))) return false;
      if (acao && !i.campos.some((c) => c.acao === acao)) return false;
      if (pendentes && i.campos.filter((c) => c.acao !== "enriquecer")
        .every((c) => decisoes[i.codigo + "|" + c.atributo])) return false;
      return true;
    });
  }

  /* -------------------------------------------------------------- desenho */
  function chipCandidato(item, campo, valor, prob) {
    const marcado = decisoes[item.codigo + "|" + campo.atributo];
    const escolhido = marcado && marcado.valor === valor;
    return el("button", {
      class: "btn sm" + (escolhido ? " primary" : ""),
      title: `aplicar ${valor}` + (prob ? ` (${pct(prob)} de probabilidade)` : ""),
      onclick: () => { gravaDecisao(item.codigo, campo.atributo, valor, "aceita"); render(); },
    },
      el("span", {}, valor),
      prob != null
        ? el("span", { style: "margin-left:7px" }, pilulaConf(prob))
        : el("span", { class: "badge", style: "margin-left:7px" }, "do texto"));
  }

  function notaCalibracao(campo) {
    const cal = (fila.calibracao || {}).acerto_medido || {};
    const chave = campo.veredito === "PERDIDO" ? "PERDIDO" : campo.banda;
    const c = cal[chave];
    if (!c) return null;
    const txt = c.acerto
      ? `faixa medida: acerta ${pct(c.acerto)} em ${inteiro(c.casos)} casos`
      : c.nota;
    return el("div", { class: "faint", style: "font-size:11px;margin-top:4px;font-style:italic" }, txt);
  }

  function linhaCampo(item, campo) {
    const d = decisoes[item.codigo + "|" + campo.atributo];
    const porque = [campo.sinal, campo.nota].filter(Boolean).join(" · ");
    return el("div", {
      class: "card",
      style: "padding:10px 12px;margin-top:8px;background:var(--bg-alt)",
    },
      el("div", { style: "display:flex;gap:10px;align-items:center;flex-wrap:wrap" },
        el("b", { style: "font-size:12.5px" }, campo.atributo),
        el("span", { class: "badge " + (CLASSE_ACAO[campo.acao] || "") }, ROTULO_ACAO[campo.acao] || campo.acao),
        campo.banda ? el("span", { class: "pill" }, campo.banda.toLowerCase()) : null,
        campo.suporte ? el("span", { class: "faint", style: "font-size:11.5px" },
          `${inteiro(campo.suporte)} casos parecidos`) : null,
        d ? el("span", { class: "badge b-green", style: "margin-left:auto" },
          d.decisao === "ausente" ? "marcado ausente" : "✓ " + d.valor) : null),
      campo.trecho
        ? el("div", { class: "faint", style: "font-size:12px;margin-top:6px" },
          "no texto: ", el("code", { class: "mono" }, campo.trecho))
        : null,
      porque ? el("div", { class: "faint", style: "font-size:11.5px;margin-top:4px" }, porque) : null,
      campo.pergunta ? el("div", { style: "font-size:12px;margin-top:6px" }, campo.pergunta) : null,
      notaCalibracao(campo),
      el("div", { class: "chip-row", style: "margin-top:8px" },
        campo.candidatos.map(([v, p]) => chipCandidato(item, campo, v, p)),
        el("button", {
          class: "btn sm ghost",
          onclick: () => {
            const v = prompt(`Valor de ${campo.atributo} para ${item.codigo}:`,
              (campo.candidatos[0] || [""])[0]);
            if (v) { gravaDecisao(item.codigo, campo.atributo, v.toUpperCase(), "manual"); render(); }
          },
        }, "outro valor…"),
        el("button", {
          class: "btn sm ghost",
          onclick: () => { gravaDecisao(item.codigo, campo.atributo, "", "ausente"); render(); },
        }, "não está no texto")));
  }

  function cartaoItem(item) {
    const acionaveis = item.campos.filter((c) => c.acao !== "enriquecer");
    const externos = item.campos.filter((c) => c.acao === "enriquecer");
    const resolvidos = acionaveis.filter((c) => decisoes[item.codigo + "|" + c.atributo]).length;
    return el("div", { class: "card", style: "margin-bottom:12px" },
      el("div", { class: "card-h" },
        el("h3", {}, el("span", { class: "mono" }, item.codigo)),
        el("span", { class: "sub" },
          `${item.substantivo} ${item.qualificador || ""} · ${item.id_pdm}`),
        el("div", { class: "r", style: "margin-left:auto;display:flex;gap:8px;align-items:center" },
          item.estado === "REVISAO_HUMANA"
            ? el("span", { class: "badge b-err" }, "conflito: segunda pessoa") : null,
          item.escalado_llm ? el("span", { class: "pill" }, "passou pelo LLM") : null,
          el("span", { class: "badge" }, `${resolvidos}/${acionaveis.length} decididos`),
          el("span", { class: "mono", style: "font-size:12px" }, brl(item.capital)))),
      el("div", { style: "padding:12px 16px" },
        el("div", { class: "pdm-preview" }, item.texto || "(sem texto)"),
        item.descricao_pdm
          ? el("div", { class: "faint", style: "font-size:11.5px;margin-top:6px" },
            "saída atual: ", el("span", { class: "mono" }, item.descricao_pdm))
          : null,
        acionaveis.map((c) => linhaCampo(item, c)),
        externos.length
          ? el("div", { class: "faint", style: "font-size:11.5px;margin-top:10px" },
            `${externos.length} campo(s) que o texto não traz (${externos.map((c) => c.atributo).join(", ")}): ` +
            "fonte externa, não leitura")
          : null));
  }

  function render() {
    const alvo = $("#fi-lista");
    if (!alvo || !fila) return;
    const lista = filtrados();
    const paginas = Math.max(1, Math.ceil(lista.length / FI_PAGINA));
    pagina = Math.min(Math.max(1, pagina), paginas);
    const fatia = lista.slice((pagina - 1) * FI_PAGINA, pagina * FI_PAGINA);

    const n = Object.keys(decisoes).length;
    const nd = $("#fi-decididos");
    if (nd) nd.textContent = n ? `${inteiro(n)} decisões nesta sessão` : "nenhuma decisão ainda";
    const cont = $("#fi-conta");
    if (cont) cont.textContent = `${inteiro(lista.length)} item(ns) · página ${pagina} de ${paginas}`;

    alvo.replaceChildren(
      ...(fatia.length ? fatia.map(cartaoItem)
        : [el("div", { class: "faint", style: "padding:16px" }, "Nada com esse filtro.")]));
    const pg = $("#fi-pager");
    if (pg) {
      pg.replaceChildren(
        el("button", { class: "btn sm", onclick: () => { pagina--; render(); } }, "‹"),
        el("span", { class: "faint", style: "font-size:12px" }, `${pagina} / ${paginas}`),
        el("button", { class: "btn sm", onclick: () => { pagina++; render(); } }, "›"));
    }
  }

  function exporta() {
    const linhas = Object.values(decisoes).map((d) => JSON.stringify(d)).join("\n");
    if (!linhas) { if (window.toast) toast("Nenhuma decisão para exportar."); return; }
    const url = URL.createObjectURL(new Blob([linhas + "\n"], { type: "application/x-ndjson" }));
    const a = el("a", { href: url, download: "revisao_humana_decisoes.jsonl" });
    document.body.append(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
    if (window.toast) toast(`${Object.keys(decisoes).length} decisões exportadas.`);
  }

  function limpa() {
    if (!confirm("Apagar as decisões desta sessão?")) return;
    decisoes = {};
    try { localStorage.removeItem(FI_CHAVE); } catch (e) {}
    render();
  }

  /* ----------------------------------------------------------------- ligação */
  function liga() {
    if (!$("#page-intervencao")) return;
    for (const id of ["#fi-busca", "#fi-acao", "#fi-classe", "#fi-pendentes", "#fi-ordem"]) {
      const n = $(id);
      if (n) n.addEventListener(n.tagName === "INPUT" && n.type !== "checkbox" ? "input" : "change",
        () => { pagina = 1; render(); });
    }
    const ex = $("#fi-exportar"); if (ex) ex.addEventListener("click", exporta);
    const lp = $("#fi-limpar"); if (lp) lp.addEventListener("click", limpa);
    carrega();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", liga);
  else liga();
})();
