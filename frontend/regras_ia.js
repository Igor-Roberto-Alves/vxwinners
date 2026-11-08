/* Interferência de IA — a regra, a linha que a provisionou e todas que ela decidiu.
 *
 * Lê artefatos/regras_ia.json (publicado em /frontend/dados/), gerado por
 * scripts/22_regras_ia.py a partir do dicionário aprendido e da auditoria do
 * pipeline.
 *
 * O problema que esta tela resolve: o dicionário aprendido é a camada mais
 * barata do pipeline e a mais perigosa. Uma pergunta feita ao LLM uma vez vira
 * regra e passa a decidir sozinha — 'ACO ZINCADO' → ACO CARBONO ZINCADO foi
 * respondido uma vez e decidiu 255 linhas. Se a resposta estiver errada, estão
 * erradas as 255, e até aqui não havia como saber quais eram.
 *
 * Por isso derrubar não é por linha. Quando alguém diz que a regra não valeu
 * numa linha, a tela mostra TODAS as outras que a mesma regra decidiu, com o
 * capital que elas carregam, e faz a pergunta que decide o tamanho do estrago:
 *
 *   só nesta linha        a regra continua valendo; aquele registro vira exceção
 *   a regra não vale      a regra cai e as N linhas que ela decidiu voltam
 *                         para revisão, listadas na hora
 *
 * A procedência vem rotulada, porque ela não é igual em toda regra:
 *   registrada   o dicionário gravou o código de origem (execuções novas)
 *   desempate    a linha está em desempate_llm.jsonl, com a evidência lida
 *   derivada     regra antiga: é a linha mais antiga em que a regra vale hoje.
 *                É pista, não registro — e a tela diz isso.
 *
 * As decisões ficam em localStorage e saem em .jsonl pelo botão "Exportar
 * decisões", no formato que o scripts/18_curar_aprendizado.py consome.
 */
(function () {
  "use strict";

  const ARQ = "frontend/dados/regras_ia.json";
  const ALT = "http://127.0.0.1:8000/frontend/dados/regras_ia.json";
  const CHAVE = "mro-regras-ia-decisoes";
  const POR_PAGINA = 20;
  const POR_PAGINA_D = 50;
  const MOSTRA_OUTRAS = 12;          // quantas linhas irmãs listar na pergunta

  const SELO_ORIGEM = {
    registrada: ["b-green", "origem registrada",
      "o dicionário gravou o código de origem quando aprendeu o termo"],
    desempate: ["b-green", "origem no desempate",
      "a linha está em desempate_llm.jsonl, com a evidência que o LLM leu"],
    derivada: ["b-warn", "origem derivada",
      "regra antiga: o pipeline não gravou a procedência. Esta é a linha mais " +
      "antiga em que a regra vale hoje — pista, não registro"],
    ausente: ["b-err", "sem origem",
      "não há linha registrada nem aplicação hoje: a regra está no dicionário sem rastro"],
  };

  let dados = null;
  let pag = 1, pagD = 1, atual = 0;
  let decisoes = {};
  let pendente = null;               // { regra, codigo } aguardando a pergunta

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

  const regraDe = (id) => dados.regras.find((r) => r.id === id);
  const julgamento = (id) => decisoes["regra|" + id];
  const excecao = (id, codigo) => decisoes[`linha|${id}|${codigo}`];
  const temExcecao = (id) => dados.regras.length &&
    Object.keys(decisoes).some((k) => k.startsWith(`linha|${id}|`));

  /* termo → valor, do jeito que a regra age: o que o cadastro escreveu e o que
   * a IA gravou no lugar */
  function regraTexto(r) {
    return el("span", { class: "troca" },
      el("span", { class: "mono" }, r.termo),
      el("span", { class: "seta" }, "→"),
      el("span", { class: "para" }, r.valor));
  }

  /* ------------------------------------------------------------- decisões */
  function carregaDecisoes() {
    try { decisoes = JSON.parse(localStorage.getItem(CHAVE) || "{}"); }
    catch (e) { decisoes = {}; }
  }
  function grava(chave, obj) {
    decisoes[chave] = {
      ...obj,
      usuario: ($("#usuario") && $("#usuario").value.split("|")[0]) || "anonimo",
      quando: new Date().toISOString(),
      origem: "regras_ia",
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
    const r = dados.resumo, o = r.origem || {};
    $("#ia-kpis").replaceChildren(
      cartao("Regras criadas pelo LLM", inteiro(r.regras),
        `${inteiro(r.regras_usadas)} decidiram alguma linha · ${inteiro(r.regras_em_revisao)} em revisão`,
        "fonte: " + dados.fonte.dicionario),
      cartao("Linhas decididas por regra", inteiro(r.aplicacoes),
        `${inteiro(r.linhas_com_ia)} linhas da base têm alguma interferência de IA`,
        "fonte: " + dados.fonte.decisoes),
      cartao("Capital sob regra de IA", brlCurto(r.capital_em_regras),
        "estoque dos itens que uma regra decidiu",
        "fonte: " + dados.fonte.capital, "var(--warn)"),
      cartao("Regras que acrescentam ao texto", inteiro(r.regras_que_acrescentam),
        `${inteiro(r.linhas_com_acrescimo)} linhas · ${brlCurto(r.capital_com_acrescimo)} · ` +
        `${inteiro(r.regras_uma_confirmacao)} regras vistas uma única vez`,
        "o valor gravado tem palavra que o termo lido não traz — 'ACO CARBONO' virando " +
        "'ACO CARBONO ZINCADO'. Pode ser escolha forçada pela lista do PDM, pode ser palpite",
        "var(--err)"));

    const g = $("#ia-gerado");
    if (g) g.textContent = "· dados de " + (dados.gerado_em || "").replace("T", " ");
    const n = $("#n-ia");
    if (n) n.textContent = inteiro(r.regras);
    const abas = $("#ia-abas");
    if (abas) {
      abas.querySelector('[data-aba="regras"]').textContent =
        `Regras do dicionário · ${inteiro(r.regras)}`;
      abas.querySelector('[data-aba="decisoes"]').textContent =
        `Decisões diretas de IA · ${inteiro(r.decisoes_ia_sem_regra)}`;
    }
  }

  /* -------------------------------------------------------------- regras */
  function filtra() {
    const q = (($("#ia-r-busca") && $("#ia-r-busca").value) || "").trim().toUpperCase();
    const f = $("#ia-r-filtro") ? $("#ia-r-filtro").value : "usadas";
    const ordem = ($("#ia-r-ordem") && $("#ia-r-ordem").value) || "linhas";
    let lista = dados.regras.filter((r) => {
      if (f === "usadas" && !r.n_aplicacoes) return false;
      if (f === "revisao" && !r.revisar) return false;
      if (f === "uma" && r.confirmacoes !== 1) return false;
      if (f === "conflito" && !r.fonte.includes("conflito")) return false;
      if (f === "rebaixada" && !r.curado_rebaixou) return false;
      if (f === "acrescenta" && !(r.acrescenta || []).length) return false;
      if (f === "decididas" && !(julgamento(r.id) || temExcecao(r.id))) return false;
      if (!q) return true;
      return r.termo.toUpperCase().includes(q) || r.valor.toUpperCase().includes(q) ||
        r.atributo.includes(q) || (r.classes || []).some((c) => c.includes(q)) ||
        (r.aplicacoes || []).some((x) => x.codigo.includes(q));
    });
    if (ordem === "capital") lista = lista.slice().sort((a, b) => b.capital - a.capital);
    else if (ordem === "confirmacoes") lista = lista.slice().sort((a, b) =>
      a.confirmacoes - b.confirmacoes || b.n_aplicacoes - a.n_aplicacoes);
    return lista;
  }

  function selos(r) {
    const s = [];
    const j = julgamento(r.id);
    if (j) s.push(el("span", {
      class: "badge " + (j.decisao === "regra_invalida" ? "b-err" : "b-green"),
      title: j.comentario || "",
    }, j.decisao === "regra_invalida" ? "regra derrubada" : "regra confirmada"));
    if (temExcecao(r.id)) s.push(el("span", { class: "badge b-warn" }, "com exceção"));
    if (r.fonte.includes("conflito")) s.push(el("span", {
      class: "badge b-err", title: "o mesmo termo recebeu dois valores diferentes",
    }, "conflito"));
    if (r.acrescenta && r.acrescenta.length) s.push(el("span", {
      class: "badge b-err",
      title: `o texto traz “${r.termo}” e a regra gravou “${r.valor}”: ` +
        `${r.acrescenta.join(", ")} não está escrito no texto. Pode ser escolha forçada ` +
        "pela lista do PDM (se só um valor contém o termo) ou palpite — é o que a revisão decide",
    }, "+" + r.acrescenta.join(" +")));
    if (r.interpretacao) s.push(el("span", {
      class: "badge b-warn", title: "o curador marcou como interpretação de domínio, " +
        "não tradução de notação",
    }, "interpretação"));
    if (r.curado_rebaixou) s.push(el("span", {
      class: "badge b-warn", title: "o curador (scripts/18_curar_aprendizado.py) rebaixou " +
        "esta regra de regra para sugestão",
    }, "rebaixada"));
    if (r.revisar) s.push(el("span", {
      class: "badge", title: "marcada para revisão no próprio dicionário",
    }, "revisar"));
    return s;
  }

  function tabelaRegras(lista) {
    const paginas = Math.max(1, Math.ceil(lista.length / POR_PAGINA));
    pag = Math.min(Math.max(1, pag), paginas);
    const fatia = lista.slice((pag - 1) * POR_PAGINA, pag * POR_PAGINA);

    const thead = el("thead", {}, el("tr", {},
      el("th", {}, "ATRIBUTO"),
      el("th", {}, "A REGRA (o que escreveram → o que a IA gravou)"),
      el("th", { class: "num", title: "quantas vezes o LLM viu o termo" }, "CONF."),
      el("th", { class: "num", title: "linhas da base que esta regra decidiu" }, "LINHAS"),
      el("th", { class: "num" }, "CAPITAL"),
      el("th", {}, "ORIGEM"),
      el("th", {}, "ESTADO")));

    const tbody = el("tbody", {}, fatia.map((r) => {
      const i = lista.indexOf(r);
      const [cls, rotulo, dica] = SELO_ORIGEM[r.origem_tipo] || SELO_ORIGEM.ausente;
      return el("tr", {
        class: i === atual ? "sel" : "", style: "cursor:pointer",
        onclick: () => { atual = i; pendente = null; desenha(); abreDetalhe(); },
      },
        el("td", { class: "mono faint", style: "font-size:11px" }, r.atributo),
        // as classes vão embaixo da regra: como coluna própria, empurravam a de
        // estado para fora da tela
        el("td", { class: "wrap" }, regraTexto(r),
          el("div", { class: "mono faint", style: "font-size:10.5px" },
            (r.classes || []).join(" "))),
        el("td", { class: "num" }, String(r.confirmacoes)),
        el("td", { class: "num" }, inteiro(r.n_aplicacoes)),
        el("td", { class: "num" }, brl(r.capital)),
        el("td", {}, el("span", { class: "badge " + cls, title: dica }, rotulo)),
        el("td", { class: "wrap" }, selos(r)));
    }));

    $("#ia-r-table").replaceChildren(thead, tbody);
    $("#ia-r-conta").textContent =
      `${inteiro(lista.length)} regra(s) · página ${pag} de ${paginas}`;
    $("#ia-r-pager").replaceChildren(
      el("button", { class: "btn sm", onclick: () => { pag--; desenha(); } }, "‹"),
      el("span", { style: "font-size:12px" }, `${pag} / ${paginas}`),
      el("button", { class: "btn sm", onclick: () => { pag++; desenha(); } }, "›"),
      el("span", { class: "faint", style: "margin-left:auto" },
        `${inteiro(Object.keys(decisoes).length)} decisão(ões) nesta sessão`));
  }

  function desenha() {
    const lista = filtra();
    const r = dados.resumo;
    $("#ia-r-sub").textContent =
      `${inteiro(r.regras)} regras · ${inteiro(r.aplicacoes)} linhas decididas · ` +
      `${inteiro(r.aplicacoes_sem_ligacao)} aplicações que não deu para ligar a uma regra`;
    tabelaRegras(lista);
    return lista;
  }

  /* ------------------------------------------------------ detalhe da regra */
  function linhaCompacta(x, extra) {
    return el("div", { style: "display:flex;gap:10px;align-items:baseline;padding:3px 0" },
      el("span", { class: "mono", style: "font-size:11.5px;min-width:74px" }, x.codigo),
      el("span", { class: "mono faint", style: "font-size:10.5px;min-width:52px" },
        x.id_pdm || ""),
      el("span", { style: "font-size:11.5px;flex:1" }, x.descricao || ""),
      el("span", { class: "mono faint", style: "font-size:11px" }, brl(x.capital)),
      extra || null);
  }

  function painelOrigem(r) {
    const [cls, rotulo, dica] = SELO_ORIGEM[r.origem_tipo] || SELO_ORIGEM.ausente;
    return el("div", { class: "callout " + (r.origem_tipo === "derivada" ||
      r.origem_tipo === "ausente" ? "warn" : "ok") },
      el("div", { style: "font-size:12.5px" },
        el("b", { style: "font-weight:500" }, "De onde a regra saiu. "),
        el("span", { class: "badge " + cls, title: dica }, rotulo),
        el("div", { class: "faint", style: "margin-top:4px;font-size:11.5px" }, dica),
        r.origens.length
          ? el("div", { style: "margin-top:8px" },
            r.origens.map((x) => linhaCompacta(x,
              el("span", { class: "mono", style: "font-size:11px;color:var(--iainfo)" },
                x.evidencia ? "leu “" + x.evidencia + "”" : ""))))
          : el("div", { class: "faint", style: "margin-top:6px;font-size:12px" },
            "Nenhuma linha de origem registrada e nenhuma aplicação hoje."),
        el("div", { class: "faint", style: "margin-top:8px;font-size:11.5px" },
          `Vista ${r.confirmacoes}× pelo LLM · fonte ${r.fonte} · ` +
          `primeira vez em ${r.primeira_vez || "—"}` +
          (r.curado_fonte && r.curado_fonte !== r.fonte
            ? ` · no dicionário curado: ${r.curado_fonte}` : ""))));
  }

  /* A pergunta que o pedido pede: derrubou numa linha, e as outras?
   *
   * O texto diz o tamanho do estrago ANTES da escolha (quantas linhas, quanto
   * capital), porque é isso que diferencia "foi um caso" de "a regra está
   * errada" — e quem responde precisa ver as irmãs para decidir. */
  function painelValidacao() {
    const alvo = $("#ia-d-validacao");
    if (!pendente) { alvo.replaceChildren(); return; }
    const r = regraDe(pendente.regra);
    const esta = r.aplicacoes.find((x) => x.codigo === pendente.codigo) || {};
    const outras = r.aplicacoes.filter((x) => x.codigo !== pendente.codigo);
    const capitalOutras = outras.reduce((a, x) => a + x.capital, 0);
    const comentario = el("input", {
      class: "inp", id: "ia-v-comentario", style: "margin-top:8px",
      placeholder: "Por que não valeu? (vai na decisão exportada)",
    });

    alvo.replaceChildren(el("div", {
      class: "callout warn", style: "border-left:3px solid var(--warn)",
    },
      el("div", { style: "font-size:12.5px" },
        el("b", { style: "font-weight:500" }, "Você derrubou esta regra em "),
        el("span", { class: "mono" }, pendente.codigo),
        el("b", { style: "font-weight:500" }, ". Ela também decidiu em "),
        el("b", { style: "font-weight:500;color:var(--warn)" },
          `${inteiro(outras.length)} outra(s) linha(s)`),
        el("b", { style: "font-weight:500" }, ", somando "),
        el("span", { class: "mono" }, brl(capitalOutras)),
        el("b", { style: "font-weight:500" }, "."),
        el("div", { class: "faint", style: "margin-top:4px;font-size:11.5px" },
          `Nesta linha a regra gravou ${esta.valor || r.valor} em ${r.atributo}, ` +
          `a partir de “${r.termo}” no texto.`),
        outras.length
          ? el("div", { style: "margin-top:8px;max-height:220px;overflow:auto" },
            outras.slice(0, MOSTRA_OUTRAS).map((x) => linhaCompacta(x,
              el("span", { class: "mono faint", style: "font-size:11px" }, x.valor))),
            outras.length > MOSTRA_OUTRAS
              ? el("div", { class: "faint", style: "font-size:11.5px;margin-top:4px" },
                `e mais ${inteiro(outras.length - MOSTRA_OUTRAS)} linha(s) na tabela abaixo`)
              : null)
          : el("div", { class: "faint", style: "margin-top:6px;font-size:12px" },
            "Esta é a única linha que a regra decidiu."),
        comentario,
        el("div", { style: "display:flex;gap:8px;margin-top:12px;flex-wrap:wrap" },
          el("button", {
            class: "btn", "data-ia-esc": "linha",
            title: "a regra continua valendo; só este registro vira exceção",
          }, "Não valeu só nesta linha"),
          el("button", {
            class: "btn primary", "data-ia-esc": "regra",
            title: "derruba a regra e manda para revisão todas as linhas que ela decidiu",
          }, `A regra não vale · revisar ${inteiro(r.n_aplicacoes)} linha(s)`),
          el("button", { class: "btn ghost", "data-ia-esc": "cancelar" }, "Cancelar")))));
    alvo.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function tabelaUsos(r) {
    const j = julgamento(r.id);
    const thead = el("thead", {}, el("tr", {},
      el("th", {}, "CÓDIGO"), el("th", {}, "CLASSE"), el("th", {}, "DESCRIÇÃO"),
      el("th", {}, "ATRIBUTO"), el("th", {}, "VALOR QUE A REGRA GRAVOU"),
      el("th", { class: "num" }, "CONF."), el("th", { class: "num" }, "CAPITAL"),
      el("th", {}, "ESTADO"), el("th", {}, "")));

    const tbody = el("tbody", {}, r.aplicacoes.map((x) => {
      const ex = excecao(r.id, x.codigo);
      const derrubada = j && j.decisao === "regra_invalida";
      return el("tr", { class: ex || derrubada ? "dup-row" : "" },
        el("td", { class: "mono" }, x.codigo),
        el("td", { class: "mono faint", style: "font-size:11px" }, x.id_pdm || ""),
        el("td", { class: "wrap", style: "font-size:11.5px;max-width:280px" },
          x.descricao || ""),
        el("td", { class: "mono faint", style: "font-size:11px" }, x.atributo || ""),
        el("td", { class: "mono" }, x.valor || ""),
        el("td", { class: "num mono", style: "font-size:11.5px" },
          x.confianca != null ? String(x.confianca) : "—"),
        el("td", { class: "num" }, brl(x.capital)),
        el("td", {}, ex
          ? el("span", { class: "badge b-warn", title: ex.comentario || "" }, "exceção aqui")
          : derrubada
            ? el("span", { class: "badge b-err" }, "a revisar")
            : el("span", { class: "badge b-ia" }, "decidido por IA")),
        el("td", {}, ex || derrubada
          ? el("button", {
            class: "btn sm ghost",
            onclick: () => {
              delete decisoes[`linha|${r.id}|${x.codigo}`];
              if (derrubada) delete decisoes["regra|" + r.id];
              try { localStorage.setItem(CHAVE, JSON.stringify(decisoes)); } catch (e) {}
              desenha(); abreDetalhe();
            },
          }, "desfazer")
          : el("button", {
            class: "btn sm",
            onclick: () => { pendente = { regra: r.id, codigo: x.codigo }; abreDetalhe(); },
          }, "não valeu aqui")));
    }));
    $("#ia-d-usos").replaceChildren(thead, tbody);
  }

  function abreDetalhe() {
    const lista = filtra();
    if (!lista.length) {
      $("#ia-d-titulo").textContent = "Nada com esse filtro";
      for (const id of ["#ia-d-origem", "#ia-d-validacao", "#ia-d-usos", "#ia-d-acoes",
        "#ia-d-selo"]) $(id).replaceChildren();
      $("#ia-d-usos-tit").textContent = "";
      return;
    }
    atual = Math.min(Math.max(0, atual), lista.length - 1);
    const r = lista[atual];
    if (pendente && pendente.regra !== r.id) pendente = null;

    $("#ia-d-titulo").replaceChildren(
      el("span", { class: "mono faint", style: "font-size:12px" }, r.atributo + ": "),
      regraTexto(r));
    $("#ia-d-sub").textContent =
      `${inteiro(r.n_aplicacoes)} linha(s) decidida(s) · ${brl(r.capital)} em estoque · ` +
      `vista ${r.confirmacoes}× · ${(r.classes || []).join(", ")}`;
    $("#ia-d-selo").replaceChildren(...selos(r));
    $("#ia-d-origem").replaceChildren(painelOrigem(r));
    painelValidacao();
    $("#ia-d-usos-tit").textContent = r.n_aplicacoes
      ? "Todas as linhas em que esta regra decidiu — derrubar uma pergunta pelas outras"
      : "Esta regra está no dicionário e não decidiu nenhuma linha nesta execução";
    tabelaUsos(r);

    const j = julgamento(r.id);
    $("#ia-d-acoes").replaceChildren(
      el("button", {
        class: "btn" + (j && j.decisao === "regra_confirmada" ? " primary" : ""),
        onclick: () => {
          grava("regra|" + r.id, {
            escopo: "regra", decisao: "regra_confirmada", regra: r.id,
            atributo: r.atributo, termo: r.termo, valor_sugerido: r.valor,
            comentario: "", linhas_afetadas: r.n_aplicacoes,
          });
          if (window.toast) toast(`regra confirmada · ${r.termo} → ${r.valor}`);
          desenha(); abreDetalhe();
        },
      }, "Confirmar a regra (vale em geral)"),
      el("button", {
        class: "btn ghost",
        onclick: () => {
          atual = (atual + 1) % lista.length; pendente = null;
          desenha(); abreDetalhe();
          $("#ia-detalhe").scrollIntoView({ behavior: "smooth", block: "start" });
        },
      }, "Próxima →"),
      j ? el("span", { class: "faint", style: "font-size:11.5px;align-self:center" },
        `julgada nesta sessão: ${j.decisao}`) : null);
  }

  function resolve(escopo) {
    if (!pendente) return;
    const r = regraDe(pendente.regra);
    const cm = ($("#ia-v-comentario") && $("#ia-v-comentario").value) || "";
    if (escopo === "cancelar") { pendente = null; abreDetalhe(); return; }
    if (escopo === "linha") {
      grava(`linha|${r.id}|${pendente.codigo}`, {
        escopo: "linha", decisao: "nao_vale_aqui", regra: r.id, codigo: pendente.codigo,
        atributo: r.atributo, termo: r.termo, valor_sugerido: r.valor, comentario: cm,
      });
      if (window.toast) toast(`exceção em ${pendente.codigo} · a regra segue valendo`);
    } else {
      grava("regra|" + r.id, {
        escopo: "regra", decisao: "regra_invalida", regra: r.id,
        atributo: r.atributo, termo: r.termo, valor_sugerido: r.valor, comentario: cm,
        disparada_em: pendente.codigo,
        linhas_afetadas: r.n_aplicacoes,
        codigos_a_revisar: r.aplicacoes.map((x) => x.codigo),
        capital_a_revisar: r.capital,
      });
      if (window.toast) toast(`regra derrubada · ${inteiro(r.n_aplicacoes)} linha(s) ` +
        `para revisão (${brl(r.capital)})`);
    }
    pendente = null;
    desenha(); abreDetalhe();
  }

  /* --------------------------------------------- decisões diretas de IA */
  function tilesFontes() {
    const r = dados.resumo;
    const porFonte = r.decisoes_por_fonte || {};
    const rotulo = r.rotulo_por_fonte || {};
    const sel = $("#ia-d2-fonte");
    const fontes = Object.keys(porFonte).filter((f) => f !== "aprendido");
    if (sel && sel.options.length === 1) {
      for (const f of fontes) sel.append(el("option", { value: f }, f));
    }
    $("#ia-d2-fontes").replaceChildren(
      ...Object.keys(porFonte).map((f) => el("div", {
        class: "fx", style: "padding:10px 12px",
        "data-tt": `${f}|${rotulo[f] || ""}|fonte: ${dados.fonte.decisoes}`,
      },
        el("div", { class: "faint", style: "font-size:11px" }, f),
        el("div", { class: "mono", style: "font-size:17px;margin-top:2px" },
          inteiro(porFonte[f])),
        el("div", { class: "faint", style: "font-size:11px;margin-top:2px" },
          rotulo[f] || ""))));
    $("#ia-d2-sub").textContent =
      `${inteiro(r.decisoes_ia_sem_regra)} decisões de IA sem regra por trás · ` +
      `${inteiro(r.decisoes_ia_publicadas)} publicadas aqui, as de maior capital`;
    $("#ia-d2-nota").textContent =
      "Estas decidiram naquela linha só: não viraram regra e não têm irmãs para derrubar junto. " +
      `A junção também usou LLM na chave de identidade em ${inteiro((r.juncao_com_llm || {}).codigos || 0)} ` +
      `códigos (${inteiro((r.juncao_com_llm || {}).chaves || 0)} grupos), e esses estão na tela ` +
      "Juntados e NCM, marcados com o selo LLM.";
  }

  function desenhaDecisoes() {
    const q = (($("#ia-d2-busca") && $("#ia-d2-busca").value) || "").trim().toUpperCase();
    const f = ($("#ia-d2-fonte") && $("#ia-d2-fonte").value) || "";
    const lista = dados.decisoes_ia.filter((x) => {
      if (f && x.fonte !== f) return false;
      if (!q) return true;
      return x.codigo.includes(q) || (x.atributo || "").includes(q) ||
        (x.valor || "").toUpperCase().includes(q) ||
        (x.evidencia || "").toUpperCase().includes(q) ||
        (x.descricao || "").toUpperCase().includes(q);
    });
    const paginas = Math.max(1, Math.ceil(lista.length / POR_PAGINA_D));
    pagD = Math.min(Math.max(1, pagD), paginas);
    const fatia = lista.slice((pagD - 1) * POR_PAGINA_D, pagD * POR_PAGINA_D);

    const thead = el("thead", {}, el("tr", {},
      el("th", {}, "CÓDIGO"), el("th", {}, "CLASSE"), el("th", {}, "DESCRIÇÃO"),
      el("th", {}, "ATRIBUTO"), el("th", {}, "VALOR"), el("th", {}, "LEU NO TEXTO"),
      el("th", {}, "FONTE"), el("th", { class: "num" }, "CAPITAL")));
    const tbody = el("tbody", {}, fatia.map((x) => el("tr", {},
      el("td", { class: "mono" }, x.codigo),
      el("td", { class: "mono faint", style: "font-size:11px" }, x.id_pdm || ""),
      el("td", { class: "wrap", style: "font-size:11.5px;max-width:250px" },
        x.descricao || ""),
      el("td", { class: "mono faint", style: "font-size:11px" }, x.atributo || ""),
      el("td", { class: "mono" }, x.valor || ""),
      el("td", { class: "mono faint", style: "font-size:11px" }, x.evidencia || "—"),
      el("td", {}, el("span", { class: "badge b-ia", title: x.motivo || "" }, x.fonte)),
      el("td", { class: "num" }, brl(x.capital)))));

    $("#ia-d2-table").replaceChildren(thead, tbody);
    $("#ia-d2-conta").textContent =
      `${inteiro(lista.length)} linha(s) · página ${pagD} de ${paginas}`;
    $("#ia-d2-pager").replaceChildren(
      el("button", { class: "btn sm", onclick: () => { pagD--; desenhaDecisoes(); } }, "‹"),
      el("span", { style: "font-size:12px" }, `${pagD} / ${paginas}`),
      el("button", { class: "btn sm", onclick: () => { pagD++; desenhaDecisoes(); } }, "›"));
  }

  function mostraAba(qual) {
    $("#ia-aba-regras").style.display = qual === "regras" ? "" : "none";
    $("#ia-aba-decisoes").style.display = qual === "decisoes" ? "" : "none";
    $("#ia-abas").querySelectorAll(".seg-btn").forEach((b) =>
      b.classList.toggle("on", b.dataset.aba === qual));
    if (qual === "decisoes") desenhaDecisoes();
  }

  /* --------------------------------------------------------------- saída */
  function exporta() {
    // Formato de artefatos/aprendido_sugestoes.jsonl (atributo, termo,
    // valor_sugerido, decisao_humana, comentario) + o que esta tela acrescenta:
    // escopo, codigo e a lista de linhas que a derrubada manda para revisão.
    const linhas = Object.values(decisoes).map((d) => JSON.stringify({
      atributo: d.atributo, termo: d.termo, valor_sugerido: d.valor_sugerido,
      decisao_humana: d.decisao, comentario: d.comentario || "",
      escopo: d.escopo, codigo: d.codigo || "",
      linhas_afetadas: d.linhas_afetadas || 0,
      codigos_a_revisar: d.codigos_a_revisar || [],
      usuario: d.usuario, quando: d.quando, origem: d.origem,
    })).join("\n");
    if (!linhas) { if (window.toast) toast("Nenhuma decisão para exportar."); return; }
    const url = URL.createObjectURL(new Blob([linhas + "\n"], { type: "application/x-ndjson" }));
    const a = el("a", { href: url, download: "regras_ia_decisoes.jsonl" });
    document.body.append(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
    if (window.toast) toast(`${Object.keys(decisoes).length} decisões exportadas.`);
  }

  function limpa() {
    if (!confirm("Apagar as decisões desta sessão?")) return;
    decisoes = {}; pendente = null;
    try { localStorage.removeItem(CHAVE); } catch (e) {}
    desenha(); abreDetalhe();
  }

  /* --------------------------------------------------------- carregamento */
  function falhou() {
    $("#ia-kpis").replaceChildren(el("div", {
      class: "card", style: "grid-column:1/-1;padding:16px;line-height:1.7",
    },
      el("b", {}, "Não achei os dados da interferência de IA."),
      el("div", { class: "faint", style: "margin-top:6px" }, "Gere com"),
      el("div", { class: "pdm-preview", style: "margin-top:8px" },
        "uv run --no-project --with pandas --with openpyxl python scripts/22_regras_ia.py"),
      el("div", { class: "faint", style: "margin-top:8px" },
        "e abra a plataforma pelo servidor (./rodar.sh), não pelo arquivo.")));
  }

  let carregando = false;
  async function carrega() {
    if (dados || carregando) return;
    carregando = true;
    $("#ia-r-sub").textContent = "carregando…";
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
    tilesFontes();
    desenha();
    abreDetalhe();
  }

  function liga() {
    const pagina = $("#page-ia");
    if (!pagina) return;

    for (const id of ["#ia-r-busca", "#ia-r-filtro", "#ia-r-ordem"]) {
      const n = $(id);
      if (n) n.addEventListener(n.tagName === "INPUT" ? "input" : "change",
        () => { pag = 1; atual = 0; pendente = null; desenha(); abreDetalhe(); });
    }
    for (const id of ["#ia-d2-busca", "#ia-d2-fonte"]) {
      const n = $(id);
      if (n) n.addEventListener(n.tagName === "INPUT" ? "input" : "change",
        () => { pagD = 1; desenhaDecisoes(); });
    }
    $("#ia-abas").addEventListener("click", (e) => {
      const b = e.target.closest("[data-aba]");
      if (b) mostraAba(b.dataset.aba);
    });
    $("#ia-d-validacao").addEventListener("click", (e) => {
      const b = e.target.closest("[data-ia-esc]");
      if (b) resolve(b.dataset.iaEsc);
    });
    const ex = $("#ia-exportar"); if (ex) ex.addEventListener("click", exporta);
    const lp = $("#ia-limpar"); if (lp) lp.addEventListener("click", limpa);

    // 3 MB: só busca quando a página é aberta
    if (pagina.classList.contains("active")) carrega();
    new MutationObserver(() => {
      if (pagina.classList.contains("active")) carrega();
    }).observe(pagina, { attributes: true, attributeFilter: ["class"] });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", liga);
  else liga();
})();
