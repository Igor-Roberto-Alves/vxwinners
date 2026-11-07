/* Moldura do cadastro dentro do frontend do time (plataforma.html).
 *
 * O cadastro em si é o painel (backend/app/painel/index.html), embutido em #page-cadastro: busca, pedidos, formulário,
 * duplicidade e decisão. Aqui ficam só a navegação, o usuário, o tema e as listas de Cadastros e Revisão.
 * Toda regra de negócio fica no servidor. O que vem do banco entra na página como nó de texto, nunca como HTML.
 */
(function () {
"use strict";

const BASE = location.protocol === "file:" ? "http://127.0.0.1:8000" : "";
const API = BASE + "/api/v1";
const PAGINAS_REAIS = new Set(["busca", "cadastro", "pedidos", "cadastros", "revisao"]);
const ABA_DO_PAINEL = { busca: "buscar", cadastro: "buscar", pedidos: "pedidos" };   // as três entradas do menu levam ao painel
const ESTADOS = {
  RASCUNHO: ["rascunho", "st-neutral"], AGUARDANDO_SOLICITANTE: ["aguardando solicitante", "st-warn"],
  AGUARDANDO_CLASSE: ["aguardando classe no PDM", "st-warn"], EM_REVISAO: ["em revisão", "st-warn"],
  APROVADO: ["aprovado, na fila do ERP", "st-ok"], AGUARDANDO_REATIVACAO: ["aguardando reativação", "st-warn"],
  CADASTRADO: ["cadastrado", "st-ok"], ERRO_ERP: ["erro no ERP", "st-danger"], JA_EXISTE: ["já existe", "st-ok"],
  FORA_DO_PDM: ["fora do PDM", "st-neutral"], CANCELADO: ["cancelado", "st-neutral"],
};
const EXCECOES = {
  FORA_DA_LISTA: "Valor fora da lista do PDM", FORMATO_FORA_DO_PDM: "Formato fora do PDM", UNIDADE_DIFERENTE_DO_PADRAO: "Unidade diferente do padrão",
  GRUPO_DIFERENTE_DO_PADRAO: "Grupo diferente do padrão", NCM_DIFERENTE_DA_REGRA: "NCM diferente da regra", DUPLICIDADE_IGUAL: "Já existe item igual",
  DUPLICIDADE_BLOQUEADO_IGUAL: "Existe item igual inativo", DUPLICIDADE_PROVAVEL: "Provável duplicata", REATIVACAO: "Reativação de código",
};
const L = { estado: "", analista: "" };

/* ------------------------------------------------------------ utilitários */
const $ = (s, r = document) => r.querySelector(s);
function h(tag, attrs = {}, ...filhos) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "style") el.style.cssText = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const f of filhos.flat(Infinity)) {
    if (f === null || f === undefined || f === false) continue;
    el.append(f instanceof Node ? f : document.createTextNode(String(f)));
  }
  return el;
}
const limpa = el => { while (el.firstChild) el.removeChild(el.firstChild); return el; };
const trunca = (s, n) => { s = String(s == null ? "" : s).replace(/\s+/g, " ").trim(); return s.length > n ? s.slice(0, n - 1) + "…" : s; };
const numero = n => (n == null ? "—" : Number(n).toLocaleString("pt-BR"));
const frase = s => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);
const nomeExcecao = t => EXCECOES[t] || frase(t.replaceAll("_", " ").toLowerCase());
const usuario = () => { const [u, p] = $("#usuario").value.split("|"); return { u, p }; };

function avisa(msg, ms = 3800, erro = false) {
  const el = $("#toast"); $("#toast-t").textContent = msg; el.classList.add("show"); el.classList.toggle("erro", erro);
  clearTimeout(el._t); el._t = setTimeout(() => el.classList.remove("show"), ms);
}
async function api(metodo, caminho, corpo) {
  const { u, p } = usuario();
  const r = await fetch(API + caminho, {
    method: metodo,
    headers: { "X-Usuario": u, "X-Papel": p, ...(corpo ? { "Content-Type": "application/json" } : {}) },
    body: corpo ? JSON.stringify(corpo) : undefined,
  });
  const dados = r.status === 204 ? null : await r.json().catch(() => null);
  if (!r.ok) throw new Error((dados && (dados.detail || dados.title)) || r.statusText);
  return dados;
}
async function tenta(fn) {
  try { return await fn(); }
  catch (e) { avisa(e instanceof TypeError ? "Não consegui falar com a API. Confira se o servidor está no ar." : frase(e.message) + ".", 6000, true); return null; }
}
function marcaEstado(estado) {
  const [t, c] = ESTADOS[estado] || [String(estado || "—").replaceAll("_", " ").toLowerCase(), "st-neutral"];
  return h("span", { class: `st ${c}` }, t);
}
function marcaStatus(status) {
  if (!status) return null;
  return h("span", { class: `st ${status === "ATIVO" ? "st-ok" : status === "BLOQUEADO" ? "st-danger" : "st-neutral"}` }, status);
}

/* ------------------------------------------------------------ o painel embutido */
const quadro = () => $("#painel");
const painelPronto = new Promise(resolve => {
  const pronto = () => { const w = quadro().contentWindow; if (w && w.painel) { sincronizaPainel(); resolve(w.painel); } };
  quadro().addEventListener("load", pronto);
  pronto();
});
function sincronizaPainel() {
  const p = quadro().contentWindow.painel;
  p.usuario($("#usuario").value);
  p.tema(document.documentElement.dataset.theme === "light" ? "claro" : "escuro");
}
function abrirNoPainel(id) {
  painelPronto.then(p => { p.abrir(id); mostraPainel("cadastro"); history.replaceState(null, "", `#/cadastro/${id}`); });
}
function mostraPainel(p) {
  goBase("cadastro");
  document.querySelectorAll("[data-nav]").forEach(e => e.classList.toggle("active", e.dataset.nav === p));
  $("#crumb-page").textContent = ({ busca: "Buscar material", cadastro: "Cadastrar novo item", pedidos: "Pedidos de cadastro" })[p];
  marcaDados(p);
}

/* ------------------------------------------------------------ navegação */
const goBase = window.go;
const AO_ENTRAR = { cadastros: () => carregaCadastros(), revisao: () => carregaRevisao() };
function marcaDados(p) {
  const pill = $("#pill-dados"), real = PAGINAS_REAIS.has(p);
  pill.textContent = real ? "dados reais" : "demonstração";
  pill.title = real ? "Esta tela grava no banco de desenvolvimento" : "Tela de demonstração: ainda não ligada à API";
  pill.classList.toggle("green", real);
}
window.go = function (p, { semRota = false } = {}) {
  if (!semRota) history.replaceState(null, "", "#/" + p);
  if (ABA_DO_PAINEL[p]) { mostraPainel(p); painelPronto.then(x => x.aba(ABA_DO_PAINEL[p])); return; }
  goBase(p); marcaDados(p);
  if (AO_ENTRAR[p]) AO_ENTRAR[p]();
};
function rota() {
  const [, p, id] = (location.hash || "").split("/");
  if (p === "cadastro" && id) { abrirNoPainel(id); return; }
  window.go(p && (ABA_DO_PAINEL[p] || $("#page-" + p)) ? p : "inicio", { semRota: true });
}
async function atualizaContagens() {
  const r = await api("GET", "/resumo").catch(() => null);
  if (!r) return;
  const andamento = Object.keys(ESTADOS).filter(e => !["CADASTRADO", "JA_EXISTE", "FORA_DO_PDM", "CANCELADO"].includes(e)).reduce((n, e) => n + (r.cadastros[e] || 0), 0);
  $("#n-pedidos").textContent = numero(r.pedidos.NOVO || 0);
  $("#n-cadastros").textContent = numero(andamento);
  $("#n-revisao").textContent = numero(r.excecoes_pendentes);
}

/* ------------------------------------------------------------ cadastros e revisão */
function tabelaCadastros(itens, vazio) {
  if (!itens.length) return h("div", { class: "cad-vazio" }, vazio);
  return h("table", { class: "tbl" },
    h("thead", {}, h("tr", {}, ["Material", "Pedido", "Estado", "Responsável", ""].map(t => h("th", {}, t)))),
    h("tbody", {}, itens.map(c => h("tr", { "data-cadastro": c.id },
      h("td", { class: "wrap" }, c.descricao_curta || c.nome || "sem classe"), h("td", { class: "mono" }, c.pedido_id || "—"),
      h("td", {}, marcaEstado(c.estado)), h("td", {}, c.analista || "—"),
      h("td", {}, h("button", { class: "btn sm", onclick: () => abrirNoPainel(c.id) }, "Abrir"))))));
}
async function carregaCadastros() {
  const par = new URLSearchParams({ limite: 100 });
  if (L.estado) par.set("estado", L.estado);
  if (L.analista) par.set("analista", L.analista);
  const r = await tenta(() => api("GET", "/cadastros?" + par));
  atualizaContagens();
  if (!r) return;
  $("#cads-total").textContent = `${numero(r.total)} cadastro${r.total === 1 ? "" : "s"}`;
  limpa($("#cads-tabela")).append(tabelaCadastros(r.itens, "Nenhum cadastro com estes filtros."));
}
async function carregaRevisao() {
  atualizaContagens();
  const box = limpa($("#rev-tabela")), erp = limpa($("#rev-erp")), papel = usuario().p;
  $("#rev-sync").style.display = papel === "revisor" ? "" : "none";
  if (papel !== "revisor") box.append(h("div", { class: "cad-vazio" }, "Só quem tem papel de revisor decide exceções. Troque o usuário no topo para “bia · revisora”."));
  else {
    const ex = await tenta(() => api("GET", "/excecoes"));
    if (ex) {
      const porCad = new Map();
      for (const e of ex) { if (!porCad.has(e.cadastro_id)) porCad.set(e.cadastro_id, []); porCad.get(e.cadastro_id).push(e); }
      if (!porCad.size) box.append(h("div", { class: "cad-vazio" }, "Nenhuma exceção aguardando decisão."));
      else box.append(h("table", { class: "tbl" },
        h("thead", {}, h("tr", {}, ["Material", "Pedido", "Exceção", "Justificativa", "Autor", ""].map(t => h("th", {}, t)))),
        h("tbody", {}, [...porCad.entries()].map(([id, lista]) => h("tr", { "data-cadastro": id },
          h("td", {}, lista[0].nome || "—"), h("td", { class: "mono" }, lista[0].pedido_id || "—"),
          h("td", { class: "wrap" }, lista.map(e => nomeExcecao(e.tipo) + (e.atributo ? ` (${e.atributo})` : "")).join("; ")),
          h("td", { class: "wrap" }, trunca(lista.map(e => e.justificativa).join(" · "), 120)), h("td", {}, lista[0].autor),
          h("td", {}, h("button", { class: "btn sm primary", onclick: () => abrirNoPainel(id) }, "Decidir")))))));
    }
  }
  if (papel === "leitor") { erp.append(h("div", { class: "cad-vazio" }, "Sem permissão para ver os envios.")); return; }
  const envios = await tenta(() => api("GET", "/erp/envios"));
  if (!envios) return;
  if (!envios.length) { erp.append(h("div", { class: "cad-vazio" }, "Nenhum envio ao ERP ainda.")); return; }
  erp.append(h("table", { class: "tbl" },
    h("thead", {}, h("tr", {}, ["Tipo", "Estado", "Tentativas", "Protocolo", ""].map(t => h("th", {}, t)))),
    h("tbody", {}, envios.map(e => h("tr", {}, h("td", {}, e.tipo), h("td", {}, marcaEstado(e.estado)), h("td", { class: "num" }, e.tentativas), h("td", { class: "mono" }, e.protocolo || "—"),
      h("td", {}, h("button", { class: "btn sm", onclick: () => abrirNoPainel(e.cadastro_id) }, "Abrir")))))));
}
async function sincronizaErp() {
  const r = await tenta(() => api("POST", "/erp/sincronizar"));
  if (r) { avisa("Sincronização concluída."); carregaRevisao(); }
}

/* ------------------------------------------------------------ material da base */
async function abreMaterial(codigo) {
  const r = await tenta(() => api("GET", `/materiais/${encodeURIComponent(codigo)}`));
  if (!r) return;
  const m = r.material, k = r.classificacao, corpo = limpa($("#mat-corpo"));
  $("#mat-titulo").textContent = m.codigo;
  corpo.append(
    h("div", { style: "display:flex;gap:8px;align-items:center;margin-bottom:10px" }, marcaStatus(m.status), h("span", { class: "badge b-gray" }, m.grupo || "—")),
    h("div", { class: "pdm-preview", style: "margin-bottom:14px" }, m.descricao_longa || m.descricao_curta || "—"),
    h("table", { class: "tbl", style: "margin-bottom:14px" }, h("tbody", {}, [["Centro", m.centro], ["Estoque", `${numero(m.estoque)} ${m.unidade || ""}`], ["NCM", m.ncm], ["Fabricante", m.fabricante], ["Referência", m.referencia_fabricante],
      ["Classe lida", k ? `${k.id_pdm} · ${k.nome || ""}` : "não classificado"]].map(([a, b]) => h("tr", {}, h("td", { class: "muted" }, a), h("td", { class: "wrap" }, b || "—"))))));
  if (r.atributos.length) corpo.append(h("div", {}, h("div", { class: "lbl" }, "Atributos lidos"), h("div", { class: "chip-row" }, r.atributos.map(a => h("span", { class: "chip", title: a.trecho || "" }, `${a.atributo}: ${a.valor}`)))));
  $("#ov-mat").classList.add("open"); $("#drawer-mat").classList.add("open");
}
function fechaMaterial() { $("#ov-mat").classList.remove("open"); $("#drawer-mat").classList.remove("open"); }

/* ------------------------------------------------------------ partida */
function liga() {
  $("#cads-estado").addEventListener("change", e => { L.estado = e.target.value; carregaCadastros(); });
  $("#cads-meus").addEventListener("change", e => { L.analista = e.target.checked ? usuario().u : ""; carregaCadastros(); });
  $("#rev-sync").addEventListener("click", sincronizaErp);
  $("#ir-codigo").addEventListener("keydown", e => { if (e.key === "Enter" && e.target.value.trim()) { abreMaterial(e.target.value.trim()); e.target.value = ""; } });
  $("#ov-mat").addEventListener("click", fechaMaterial);
  $("#mat-fechar").addEventListener("click", fechaMaterial);
  $("#usuario").addEventListener("change", e => {
    try { localStorage.setItem("cadastro-usuario", e.target.value); } catch (x) { /* preferência local, opcional */ }
    $("#avatar").textContent = usuario().u.slice(0, 2).toUpperCase();
    L.analista = $("#cads-meus").checked ? usuario().u : "";
    painelPronto.then(sincronizaPainel);
    const ativa = $(".page.active");
    if (ativa && AO_ENTRAR[ativa.id.replace("page-", "")]) AO_ENTRAR[ativa.id.replace("page-", "")]();
  });
  new MutationObserver(() => painelPronto.then(sincronizaPainel)).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  window.addEventListener("message", e => { if (e.origin === location.origin && e.data && e.data.tipo === "cadastro-mudou") atualizaContagens(); });
  window.addEventListener("hashchange", rota);
}
async function inicia() {
  try { const salvo = localStorage.getItem("cadastro-usuario"); if (salvo) $("#usuario").value = salvo; } catch (e) { /* preferência local, opcional */ }
  $("#avatar").textContent = usuario().u.slice(0, 2).toUpperCase();
  liga();
  try {
    const s = await (await fetch(BASE + "/saude")).json();
    $("#api-status").textContent = "API ok";
    $("#api-status").title = `IA ${s.llm.habilitado ? "ligada" : "desligada"} · modelos de sugestão ${s.modelos_sugestao.pronto ? "ok" : "fora do ar"} · PDM v${s.pdm_versao}`;
    atualizaContagens();
  } catch (e) {
    $("#api-status").textContent = "API fora do ar";
    document.body.append(h("div", { class: "cad-faixa" }, "O cadastro precisa do servidor. Suba a API e abra http://localhost:8000"));
  }
  rota();
}
inicia();
})();
