/* Cadastro de materiais ligado à API real, dentro do frontend do time (mockup_plataforma.html).
 *
 * Esta camada só mostra e pede: toda regra de negócio fica no servidor (docs/06-plano-modo-cadastro.md, seção 12).
 * O que vem do banco ou de pedidos entra na página como nó de texto, nunca como HTML.
 */
(function () {
"use strict";

const BASE = location.protocol === "file:" ? "http://127.0.0.1:8000" : "";
const API = BASE + "/api/v1";
const CENTROS = ["1100 - MINA SERRA AZUL", "1200 - USINA DE BENEFICIAMENTO", "1300 - TERMINAL PORTUARIO",
  "2100 - UTE SERRA AZUL", "2200 - PCH RIO CLARO", "9000 - CD CENTRAL"];
const UNIDADES = ["PC", "M", "PR", "KG", "L", "CJ", "CX", "RL", "GL", "TB"];
const PAGINAS_REAIS = new Set(["busca", "cadastro", "pedidos", "cadastros", "revisao"]);
const ESTADOS = {
  RASCUNHO: ["rascunho", "st-neutral"], AGUARDANDO_SOLICITANTE: ["aguardando solicitante", "st-warn"],
  AGUARDANDO_CLASSE: ["aguardando classe no PDM", "st-warn"], EM_REVISAO: ["em revisão", "st-warn"],
  APROVADO: ["aprovado, na fila do ERP", "st-ok"], AGUARDANDO_REATIVACAO: ["aguardando reativação", "st-warn"],
  CADASTRADO: ["cadastrado", "st-ok"], ERRO_ERP: ["erro no ERP", "st-danger"], JA_EXISTE: ["já existe", "st-ok"],
  FORA_DO_PDM: ["fora do PDM", "st-neutral"], CANCELADO: ["cancelado", "st-neutral"],
  NOVO: ["novo", "st-neutral"], EM_ANDAMENTO: ["em andamento", "st-warn"], DEVOLVIDO: ["devolvido", "st-warn"],
  CADASTRADO_EM_ANDAMENTO: ["aprovado", "st-ok"],
};
const NIVEIS = {
  IGUAL: ["mesmo item", "b-err"], PROVAVEL: ["provável duplicata", "b-warn"], DIVERGENTE: ["quase igual, mas difere", "b-gray"],
  PARECIDO: ["texto parecido", "b-gray"], EQUIVALENTE: ["equivalente (item distinto)", "b-info"],
};
const EXCECOES = {
  FORA_DA_LISTA: "Valor fora da lista do PDM", FORMATO_FORA_DO_PDM: "Formato fora do PDM", UNIDADE_DIFERENTE_DO_PADRAO: "Unidade diferente do padrão",
  GRUPO_DIFERENTE_DO_PADRAO: "Grupo diferente do padrão", NCM_DIFERENTE_DA_REGRA: "NCM diferente da regra", DUPLICIDADE_IGUAL: "Já existe item igual",
  DUPLICIDADE_BLOQUEADO_IGUAL: "Existe item igual inativo", DUPLICIDADE_PROVAVEL: "Provável duplicata", REATIVACAO: "Reativação de código",
};
const ORIGENS = { DIGITADO: "digitado", OPCAO: "opção escolhida", PEDIDO_REGRA: "lido do pedido", PEDIDO_LLM: "lido por IA", LLM: "lido por IA", TABELA: "tabela local" };

const S = { cad: null, pedido: null, perguntas: [], excecoes: [], opcoes: {}, abertoOpcoes: null, just: {}, historico: null, modeloChave: null };
const B = { texto: "", id_pdm: null, nome: null, valores: {}, resp: null, picked: null, seq: 0, just: "" };
const P = { estado: "NOVO", urgencia: "", q: "", offset: 0, limite: 25 };
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
    else if (k === "value") el.value = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const f of filhos.flat(Infinity)) {
    if (f === null || f === undefined || f === false) continue;
    el.append(f instanceof Node ? f : document.createTextNode(String(f)));
  }
  return el;
}
const limpa = el => { while (el.firstChild) el.removeChild(el.firstChild); return el; };
const slug = s => s.replace(/[^A-Za-z0-9]+/g, "_");
const trunca = (s, n) => { s = String(s == null ? "" : s).replace(/\s+/g, " ").trim(); return s.length > n ? s.slice(0, n - 1) + "…" : s; };
const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
const pct = c => Math.round((+c || 0) * 100) + "%";
const frase = s => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);
const nomeExcecao = t => EXCECOES[t] || frase(t.replaceAll("_", " ").toLowerCase());
const numero = n => (n == null ? "—" : Number(n).toLocaleString("pt-BR"));

function avisa(msg, ms = 3800, erro = false) {
  const el = $("#toast"); $("#toast-t").textContent = msg; el.classList.add("show"); el.classList.toggle("erro", erro);
  clearTimeout(el._t); el._t = setTimeout(() => el.classList.remove("show"), ms);
}
const usuario = () => { const [u, p] = $("#usuario").value.split("|"); return { u, p }; };

async function api(metodo, caminho, corpo) {
  const { u, p } = usuario();
  const r = await fetch(API + caminho, {
    method: metodo,
    headers: { "X-Usuario": u, "X-Papel": p, ...(corpo ? { "Content-Type": "application/json" } : {}) },
    body: corpo ? JSON.stringify(corpo) : undefined,
  });
  const dados = r.status === 204 ? null : await r.json().catch(() => null);
  if (!r.ok) {
    const e = new Error((dados && (dados.detail || dados.title)) || r.statusText);
    e.status = r.status; e.problema = dados; throw e;
  }
  return dados;
}
async function tenta(fn) {
  try { return await fn(); }
  catch (e) {
    const prob = e.problema;
    if (prob && prob.title === "bloqueios") avisa("Ainda não dá para aprovar: " + prob.bloqueios.map(b => b.mensagem).join(" · "), 7000, true);
    else if (prob && prob.title === "versao_desatualizada") { avisa("Outra pessoa alterou este rascunho; recarreguei."); if (S.cad) await abreCadastro(S.cad.id); }
    else if (e instanceof TypeError) avisa("Não consegui falar com a API. Confira se o servidor está no ar.", 6000, true);
    else avisa(e.message.charAt(0).toUpperCase() + e.message.slice(1) + ".", 6000, true);
    return null;
  }
}

/* Pergunta curta: devolve os valores preenchidos, ou null se a pessoa desistir. */
function dialogo({ titulo, texto, campos, confirmar = "Confirmar", perigo = false }) {
  return new Promise(resolve => {
    const entradas = campos.map(c => {
      const el = c.linhas ? h("textarea", { class: "inp", placeholder: c.dica || "", rows: c.linhas }) : h("input", { class: "inp", type: "text", placeholder: c.dica || "" });
      return { ...c, el };
    });
    const erro = h("div", { class: "cad-dlg-erro" });
    const fecha = v => { fundo.remove(); document.removeEventListener("keydown", tecla); resolve(v); };
    const envia = () => {
      for (const c of entradas) {
        if (c.el.value.trim().length < (c.minimo || 0)) {
          erro.textContent = `${c.rotulo}: informe ao menos ${c.minimo} caracteres.`; c.el.focus(); return;
        }
      }
      fecha(Object.fromEntries(entradas.map(c => [c.nome, c.el.value.trim()])));
    };
    const tecla = e => { if (e.key === "Escape") fecha(null); };
    const fundo = h("div", { class: "cad-dlg-fundo", onclick: e => { if (e.target === fundo) fecha(null); } },
      h("div", { class: "cad-dlg", role: "dialog", "aria-modal": "true", "aria-label": titulo },
        h("h3", {}, titulo), texto ? h("p", { class: "muted" }, texto) : null,
        entradas.map(c => h("div", { class: "field" }, h("label", { class: "lbl" }, c.rotulo), c.el)), erro,
        h("div", { class: "cad-dlg-acoes" },
          h("button", { class: "btn", onclick: () => fecha(null) }, "Voltar"),
          h("button", { class: `btn ${perigo ? "danger" : "primary"}`, onclick: envia }, confirmar))));
    document.addEventListener("keydown", tecla);
    document.body.append(fundo);
    if (entradas[0]) entradas[0].el.focus();
  });
}

function marcaEstado(estado) {
  const [t, c] = ESTADOS[estado] || [String(estado || "—").replaceAll("_", " ").toLowerCase(), "st-neutral"];
  return h("span", { class: `st ${c}` }, t);
}
function selectCentro(atual, aoMudar, attrs = {}) {
  return h("select", { class: "sel", onchange: e => aoMudar(e.target.value || null), ...attrs },
    h("option", { value: "" }, "— selecionar —"), CENTROS.map(c => h("option", { value: c, selected: c === atual }, c)));
}

/* Autocomplete de classe do PDM: usado na busca, no início do cadastro e na troca de classe. */
function campoClasse({ placeholder, aoEscolher, aoForaDoPdm }) {
  const lista = h("div", { class: "cad-ac-lista" });
  const entrada = h("input", { class: "inp", type: "text", placeholder, autocomplete: "off", "aria-label": placeholder });
  const procura = debounce(async () => {
    const q = entrada.value.trim(); limpa(lista);
    if (q.length < 2) return;
    const r = await tenta(() => api("GET", `/pdm/nomes?q=${encodeURIComponent(q)}&limite=8`));
    if (!r || entrada.value.trim() !== q) return;
    limpa(lista);
    if (r.ambiguo) lista.append(h("div", { class: "cad-ac-nota" }, "Esse nome existe em mais de uma classe. Escolha a certa:"));
    if (r.fora_do_pdm) {
      lista.append(h("div", { class: "cad-ac-nota" }, "Nada no PDM parece com isso. ",
        aoForaDoPdm ? h("button", { class: "btn sm", onclick: () => aoForaDoPdm(q) }, "Abrir rascunho sem classe") : null));
    }
    for (const i of r.itens) {
      lista.append(h("button", { class: "cad-ac-item", type: "button", onclick: () => { limpa(lista); aoEscolher(i, q); } },
        h("span", {}, h("b", {}, i.nome), " ", h("span", { class: "badge b-gray mono" }, i.id_pdm)),
        h("span", { class: "faint" }, i.grupo_descricao || i.grupo)));
    }
  }, 180);
  entrada.addEventListener("input", procura);
  return h("div", { class: "cad-ac" }, entrada, lista);
}

/* Chip de sugestão, no desenho do time. */
function chip(txt, conf, aoClicar, aplicado = false) {
  const nivel = conf == null ? "" : conf >= 0.85 ? " c-hi" : conf >= 0.6 ? " c-md" : " c-lo";
  return h("button", { type: "button", class: `conf-chip${nivel}${aplicado ? " aplicado" : ""}${aoClicar ? "" : " estatico"}`, onclick: aoClicar || null },
    h("span", { class: "val" }, txt), conf != null ? h("span", { class: "pct" }, pct(conf)) : null,
    conf != null ? h("span", { class: "meter", "aria-hidden": "true" }, h("i"), h("i"), h("i")) : null);
}

/* Etiquetas de comparação atributo a atributo. */
function comparacao(c) {
  const itens = c.comparacao.filter(x => x.estado !== "sem_valor");
  if (!itens.length) return null;
  const cls = { igual: "eq", diverge: "ne", ausente: "na" }, sinal = { igual: " ✓", diverge: " ≠", ausente: " ?" };
  return h("div", { class: "attr-cmp" }, itens.map(x =>
    h("span", { class: `attr ${cls[x.estado] || "na"}`, title: `pedido: ${x.rascunho ?? "—"} · base: ${x.candidato ?? "—"}` },
      x.atributo + (x.estado === "diverge" && x.candidato ? `: ${x.candidato}` : "") + (sinal[x.estado] || ""))));
}
function linkCodigo(c) {
  if (c.origem === "cadastro" && c.codigo.startsWith("cadastro:")) {   // outro cadastro, ainda sem código no ERP
    return h("button", { class: "cad-link", type: "button", title: "abrir o cadastro", onclick: e => { e.stopPropagation(); abreCadastro(c.codigo.slice(9)); } }, "outro cadastro em andamento");
  }
  return h("button", { class: "cad-link mono", type: "button", title: "ver o material", onclick: e => { e.stopPropagation(); abreMaterial(c.codigo); } }, c.codigo);
}
function cartaoCandidato(c, { aoEscolher, escolhido, acoes } = {}) {
  const [rotulo, cls] = NIVEIS[c.nivel] || [c.nivel, "b-gray"];
  const forte = c.nivel === "IGUAL" || c.nivel === "PROVAVEL";
  const cor = c.nivel === "IGUAL" ? "var(--danger)" : c.nivel === "PROVAVEL" ? "var(--warn)" : "var(--text-3)";
  return h("div", { class: `cand${forte ? " dup" : ""}${escolhido ? " picked" : ""}`, "data-code": c.codigo, "data-nivel": c.nivel, onclick: aoEscolher || null },
    h("div", { class: "cand-h" },
      h("div", { class: "conf" }, h("div", { class: "n", style: `color:${cor}` }, pct(c.pontos)), h("div", { class: "bar" }, h("i", { style: `width:${pct(c.pontos)};background:${cor}` }))),
      aoEscolher ? h("div", { class: "radio" }) : null,
      h("div", { style: "flex:1;min-width:0" },
        h("div", { style: "display:flex;gap:8px;align-items:center;flex-wrap:wrap" }, linkCodigo(c),
          c.origem === "cadastro" ? marcaEstado(c.status) : marcaEstado2(c.status), h("span", { class: `badge ${cls}` }, rotulo)),
        h("div", { class: "desc muted", style: "margin-top:3px", title: c.descricao || "" }, trunca(c.descricao, 130))),
      h("div", { style: "text-align:right;flex:none" }, h("div", { class: "mono" }, numero(c.estoque)),
        h("div", { class: "faint", style: "font-size:11.5px" }, c.centro ? c.centro.split(" - ")[0] : "estoque"))),
    h("div", { class: "cand-b" }, comparacao(c), h("div", { class: "faint", style: "font-size:11.5px;margin-top:6px" }, frase(c.motivo)), acoes || null));
}
function marcaEstado2(status) {
  if (!status) return null;
  return h("span", { class: `st ${status === "ATIVO" ? "st-ok" : status === "BLOQUEADO" ? "st-danger" : "st-neutral"}` }, status);
}

/* ------------------------------------------------------------ navegação */
const goBase = window.go;
const AO_ENTRAR = { busca: () => $("#q").focus(), cadastro: () => renderCadastro(), pedidos: () => carregaPedidos(), cadastros: () => carregaCadastros(), revisao: () => carregaRevisao() };
function marcaDados(p) {
  const pill = $("#pill-dados"); const real = PAGINAS_REAIS.has(p);
  pill.textContent = real ? "dados reais" : "dados fictícios";
  pill.title = real ? "Esta tela grava no banco de desenvolvimento" : "Tela de demonstração: ainda não ligada à API";
  pill.classList.toggle("green", real);
}
window.go = function (p, { semRota = false } = {}) {
  goBase(p); marcaDados(p);
  if (!semRota) history.replaceState(null, "", "#/" + p + (p === "cadastro" && S.cad ? "/" + S.cad.id : ""));
  if (AO_ENTRAR[p]) AO_ENTRAR[p]();
};
function rota() {
  const [, p, id] = (location.hash || "").split("/");
  if (p === "cadastro" && id) { abreCadastro(id); return; }
  window.go(p && $("#page-" + p) ? p : "inicio", { semRota: true });
}
async function atualizaContagens() {
  const r = await api("GET", "/resumo").catch(() => null);
  if (!r) return;
  const andamento = ["RASCUNHO", "AGUARDANDO_SOLICITANTE", "AGUARDANDO_CLASSE", "EM_REVISAO", "APROVADO", "AGUARDANDO_REATIVACAO", "ERRO_ERP"]
    .reduce((n, e) => n + (r.cadastros[e] || 0), 0);
  $("#n-pedidos").textContent = numero(r.pedidos.NOVO || 0);
  $("#n-cadastros").textContent = numero(andamento);
  $("#n-revisao").textContent = numero(r.excecoes_pendentes);
  return r;
}

/* ------------------------------------------------------------ busca */
const refinou = () => Object.keys(B.valores).length > 0;
function limpaBusca() {
  B.seq++; Object.assign(B, { texto: "", id_pdm: null, nome: null, valores: {}, resp: null, picked: null, just: "" });
  $("#q").value = ""; pintaBusca(); $("#q").focus();
}
async function buscaAgora() {
  const texto = $("#q").value.trim(); B.texto = texto;
  if (texto.length < 3) { B.seq++; B.resp = null; B.picked = null; pintaBusca(); return; }
  const seq = ++B.seq;
  $("#b-n").textContent = "buscando…";
  const r = await tenta(() => api("POST", "/busca", { texto, id_pdm: B.id_pdm, nome: B.nome, valores: refinou() ? B.valores : null }));
  if (seq !== B.seq) return;   // chegou uma resposta velha: a pessoa já digitou outra coisa
  B.resp = r;
  if (B.picked && r && !r.duplicidade.candidatos.some(c => c.codigo === B.picked.codigo)) B.picked = null;
  pintaBusca();
}
const buscaAdiada = debounce(buscaAgora, 350);

function pintaBusca() {
  const r = B.resp, leitura = limpa($("#b-leitura")), refino = limpa($("#b-refino")), cands = limpa($("#cands")), nota = limpa($("#b-nota"));
  $("#b-n").textContent = "0 candidatos";
  if (!r) {
    cands.append(h("div", { class: "cad-vazio" }, B.texto.length >= 3 ? "Não consegui buscar agora." : "Digite o que você precisa: o sistema lê o texto, propõe a classe do PDM e compara com a base."));
    pintaDecisao(); return;
  }
  const classe = r.classe;
  // o que foi entendido
  leitura.append(h("div", { class: "grid g-2", style: "gap:12px" },
    h("div", { class: "drop", style: "flex-direction:column;align-items:stretch;gap:8px" },
      h("div", { style: "font-weight:500" }, "Classe do PDM"),
      classe ? h("div", { class: "chip-row" }, h("span", { class: "chip from-txt", "data-classe": classe.id_pdm }, classe.nome || classe.id_pdm, " ",
        h("span", { class: "src" }, `${classe.id_pdm} · ${classe.confirmada ? "escolhida por você" : "proposta pela leitura"}`))) :
        h("div", { class: "faint", style: "font-size:12px" }, r.fora_do_pdm ? "Nada no PDM parece com isso. O item pode estar fora do padrão." : "Não deu para decidir pelo texto. Escolha abaixo:"),
      r.alternativas.filter(a => !classe || a.id_pdm !== classe.id_pdm || a.nome !== classe.nome).length ? h("div", { class: "chip-row" },
        r.alternativas.filter(a => !classe || a.id_pdm !== classe.id_pdm || a.nome !== classe.nome).slice(0, 5).map(a =>
          h("button", { class: "btn sm", type: "button", onclick: () => { B.id_pdm = a.id_pdm; B.nome = a.nome; B.valores = {}; buscaAgora(); } }, a.nome))) : null),
    h("div", { class: "drop", style: "flex-direction:column;align-items:stretch;gap:8px" },
      h("div", { style: "font-weight:500" }, "Interpretação do texto"),
      r.interpretacao.length ? h("div", { class: "chip-row" }, r.interpretacao.map(i =>
        h("span", { class: "chip from-txt", title: i.trecho || "" }, `${i.atributo}: ${i.valor}`, " ", h("span", { class: "src" }, "txt")))) :
        h("div", { class: "faint", style: "font-size:12px" }, "Nenhum atributo reconhecido no texto ainda."),
      r.chave ? h("div", { class: "faint", style: "font-size:11.5px" }, r.chave.completa ? "Identidade completa: a comparação com a base é exata." :
        `Para identificar o item faltam: ${r.chave.faltando.join(", ")}.`) : null)));
  // refinar
  if (classe) {
    refino.append(h("div", { class: "card", style: "margin-bottom:16px" },
      h("div", { class: "card-h" }, h("h3", {}, "Refinar por atributos"), h("span", { class: "sub" }, `${classe.id_pdm} · ajuste o que o texto não disse`),
        h("div", { class: "r" }, h("button", { class: "btn sm ghost", onclick: () => { B.valores = {}; buscaAgora(); } }, "Desfazer ajustes"))),
      h("div", { class: "card-b" }, h("div", { class: "grid g-3", style: "gap:12px" }, r.campos.filter(c => c.aplica !== false).slice(0, 9).map(campoRefino)))));
  }
  // candidatos
  const lista = r.duplicidade ? r.duplicidade.candidatos : [];
  $("#b-n").textContent = `${lista.length} candidato${lista.length === 1 ? "" : "s"}`;
  if (!lista.length) cands.append(h("div", { class: "cad-vazio" }, "Nenhum item da base coincide com o que foi lido."));
  for (const c of lista) {
    cands.append(cartaoCandidato(c, { escolhido: B.picked && B.picked.codigo === c.codigo, aoEscolher: () => { B.picked = c; B.just = ""; pintaBusca(); } }));
  }
  if (r.duplicidade && classe) {
    const iguais = lista.filter(c => c.nivel === "IGUAL").length, d = r.duplicidade;
    nota.append(h("div", { class: `callout ${iguais ? "warn" : "info"}`, style: "margin-top:6px" },
      h("div", { style: "flex:1" }, h("b", { style: "font-weight:500" }, iguais ? "Há item com todos os atributos de identidade iguais." : "Nenhum candidato tem todos os atributos de identidade iguais."),
        h("div", { class: "muted", style: "font-size:12px;margin-top:2px" },
          `Comparado por atributos: ${numero(d.comparaveis)} de ${numero(d.total_classe)} itens desta classe.`,
          d.comparaveis < d.total_classe ? " Os demais só têm texto livre, então isto não garante que o item não exista." : ""))));
  }
  pintaDecisao();
}
function campoRefino(c) {
  const salva = v => { if (v) B.valores[c.atributo] = v; else B.valores[c.atributo] = ""; buscaAgora(); };
  const rotulo = h("label", { class: "lbl" }, c.atributo, c.obrigatorio ? h("span", { class: "req" }, "*") : null);
  if (c.tipo === "LISTA") {
    return h("div", {}, rotulo, h("select", { class: "sel", "data-refino": c.atributo, onchange: e => salva(e.target.value) },
      h("option", { value: "" }, "— selecionar —"), c.valores_permitidos.map(x => h("option", { value: x, selected: x === c.valor }, x)),
      c.valor && !c.valores_permitidos.includes(c.valor) ? h("option", { value: c.valor, selected: true }, c.valor) : null));
  }
  return h("div", {}, rotulo, h("input", { class: "inp mono", type: "text", "data-refino": c.atributo, value: c.valor || "", placeholder: dica(c), onchange: e => salva(e.target.value.trim()) }));
}
function pintaDecisao() {
  const box = limpa($("#b-decisao")), c = B.picked, r = B.resp;
  const classe = r && r.classe;
  const diverge = c && c.comparacao.some(x => x.estado === "diverge" && !x.opcional);
  const inativo = c && c.status && c.status !== "ATIVO";
  if (!c) box.append(h("div", { class: "faint", style: "font-size:12.5px;padding:8px 0 14px" }, "Selecione um candidato à esquerda para usar o código dele, ou cadastre um item novo."));
  else {
    box.append(h("div", { class: "faint", style: "font-size:12px" }, "Item selecionado"), h("div", { class: "mono", id: "picked-code", style: "font-size:16px;margin:2px 0 10px" }, c.codigo));
    if (inativo) box.append(h("div", { class: "callout warn", style: "margin-bottom:10px;font-size:12.5px" }, `Este código está ${c.status}. Só pode voltar a ser usado com reativação aprovada por um segundo analista.`));
    box.append(h("label", { class: "lbl" }, "Justificativa ", h("span", { class: "hint" }, inativo || diverge ? "obrigatória (mín. 10 caracteres)" : "opcional")),
      h("textarea", { class: "inp", id: "b-just", placeholder: "Ex.: aplicação aceita folga normal; confirmado com PCM.", value: B.just, oninput: e => { B.just = e.target.value; } }));
  }
  box.append(h("label", { class: "lbl", style: "margin-top:12px" }, "Centro do solicitante"), selectCentro(lerCentro(), v => guardaCentro(v), { id: "b-centro" }));
  box.append(h("div", { style: "display:flex;flex-direction:column;gap:8px;margin-top:12px" },
    h("button", { class: "btn primary", id: "b-usar", style: "justify-content:center;height:34px", disabled: !c, onclick: usarDaBusca }, inativo ? "Pedir reativação deste código" : "Usar este código"),
    h("button", { class: "btn", id: "b-novo", style: "justify-content:center;height:34px;white-space:normal", disabled: !r, onclick: novoDaBusca },
      classe ? `Nenhum serve: cadastrar como ${classe.nome || classe.id_pdm}` : "Nenhum serve: cadastrar novo")));
}
function lerCentro() { try { return localStorage.getItem("cadastro-centro") || CENTROS[0]; } catch (e) { return CENTROS[0]; } }
function guardaCentro(v) { try { if (v) localStorage.setItem("cadastro-centro", v); } catch (e) { /* preferência local, opcional */ } }

/* Cria o rascunho com o que a busca já tem: classe visível, texto e ajustes da pessoa. */
async function criaDaBusca() {
  const r = B.resp, cl = r && r.classe, centro = $("#b-centro").value || null;
  let v = await api("POST", "/cadastros", { id_pdm: cl ? cl.id_pdm : null, nome: cl ? cl.nome : null, texto: B.texto, centro });
  if (cl) v = await api("POST", `/cadastros/${v.id}/interpretar`, { versao: v.versao, texto: B.texto });
  const campos = {};
  if (r.fabricante) campos.fabricante = r.fabricante;
  if (r.referencia_fabricante) campos.referencia_fabricante = r.referencia_fabricante;
  const valores = cl && refinou() ? B.valores : null;
  if (valores || (cl && Object.keys(campos).length)) v = await api("PATCH", `/cadastros/${v.id}`, { versao: v.versao, valores, campos });
  return v;
}
async function novoDaBusca() {
  const v = await tenta(criaDaBusca);
  if (v) { avisa(v.classe ? "Rascunho criado com o que você já informou." : "Rascunho criado. Escolha a classe do PDM."); await define(v); limpaBusca(); window.go("cadastro"); atualizaContagens(); }
}
async function usarDaBusca() {
  const c = B.picked; if (!c) return;
  const inativo = c.status && c.status !== "ATIVO", just = B.just.trim();
  const diverge = c.comparacao.some(x => x.estado === "diverge" && !x.opcional);
  if ((inativo || diverge) && just.length < 10) { avisa("Justifique a escolha: mínimo de 10 caracteres."); const el = $("#b-just"); if (el) el.focus(); return; }
  const novo = await tenta(criaDaBusca);
  if (!novo) return;
  const v = await tenta(() => inativo ? api("POST", `/cadastros/${novo.id}/reativar`, { codigo: c.codigo, justificativa: just })
    : api("POST", `/cadastros/${novo.id}/usar-existente`, { codigo: c.codigo, justificativa: just || null }));
  if (v) avisa(inativo ? "Reativação enviada ao segundo analista." : `Registrado: usar o código ${c.codigo}.`);
  // se a segunda etapa falhar, a pessoa cai no rascunho: nada fica órfão
  await define(v || novo); limpaBusca(); window.go("cadastro"); atualizaContagens();
}

/* ------------------------------------------------------------ cadastro: dados */
async function abreCadastro(id) {
  const v = await tenta(() => api("GET", `/cadastros/${id}`));
  if (v) { await define(v); window.go("cadastro"); }
}
async function define(v) {
  if (!S.cad || S.cad.id !== v.id) Object.assign(S, { opcoes: {}, abertoOpcoes: null, just: {}, historico: null, modeloChave: null, perguntas: [], excecoes: [], pedido: null });
  S.cad = v;
  if (v.pedido_id && (!S.pedido || S.pedido.id !== v.pedido_id)) S.pedido = await tenta(() => api("GET", `/pedidos/${v.pedido_id}`));
  if (v.estado === "AGUARDANDO_SOLICITANTE") S.perguntas = (await tenta(() => api("GET", `/cadastros/${v.id}/perguntas`))) || [];
  if (v.estado === "EM_REVISAO" && usuario().p === "revisor") {
    const todas = (await tenta(() => api("GET", "/excecoes"))) || [];
    S.excecoes = todas.filter(e => e.cadastro_id === v.id);
  }
  if (S.historico) S.historico = (await tenta(() => api("GET", `/cadastros/${v.id}/historico`))) || S.historico;
  renderCadastro();
}
/* Escritas de um rascunho, uma de cada vez. Sair de um campo e clicar em Aprovar dispara as duas quase juntas:
 * cada uma precisa esperar a anterior e usar a versão que ela devolveu, senão o servidor acusa um conflito que não existe. */
let filaEscrita = Promise.resolve(), escritasPendentes = 0;
function naFila(fn) {
  escritasPendentes++; legendaCadastro();
  const p = filaEscrita.then(fn, fn).finally(() => { escritasPendentes--; legendaCadastro(); });
  filaEscrita = p.catch(() => {});
  return p;
}
function legendaCadastro() {
  const v = S.cad, el = $("#cad-sub");
  if (!v || !el) return;
  const nome = v.classe ? (v.classe.nome || v.classe.id_pdm) : "sem classe";
  el.textContent = `${nome} · ${escritasPendentes ? "salvando…" : "alterações salvas automaticamente"} · versão ${v.versao} · responsável: ${v.analista || "—"}`;
}
function edita(corpo) {
  return naFila(async () => {
    const r = await tenta(() => api("PATCH", `/cadastros/${S.cad.id}`, { versao: S.cad.versao, ...corpo }));
    if (r) { S.opcoes = {}; await define(r); }
    return r;
  });
}
let decidindo = false;   // duplo clique em Aprovar não pode virar duas decisões
function decisao(caminho, corpo, mensagem) {
  if (decidindo) return Promise.resolve(null);
  decidindo = true;
  return naFila(async () => {
    try {
      const dados = typeof corpo === "function" ? corpo() : corpo;   // lê versão e exceções só na hora de enviar
      const r = await tenta(() => api("POST", `/cadastros/${S.cad.id}/${caminho}`, dados || {}));
      if (r) { avisa(typeof mensagem === "function" ? mensagem(r) : mensagem); await define(r); atualizaContagens(); }
      return r;
    } finally { decidindo = false; }
  });
}
function releTexto(texto, aoTerminar) {
  return naFila(async () => {
    const r = await tenta(() => api("POST", `/cadastros/${S.cad.id}/interpretar`, { versao: S.cad.versao, texto }));
    if (r) { S.opcoes = {}; if (aoTerminar) aoTerminar(r); await define(r); }
    return r;
  });
}
const comecaRascunho = async (i, q) => {
  const v = await tenta(async () => {
    const novo = await api("POST", "/cadastros", { id_pdm: i.id_pdm, nome: i.nome, texto: q, centro: lerCentro() });
    return api("POST", `/cadastros/${novo.id}/interpretar`, { versao: novo.versao, texto: q });
  });
  if (v) { await define(v); window.go("cadastro"); atualizaContagens(); }
};
const rascunhoSemClasse = async q => {
  const v = await tenta(() => api("POST", "/cadastros", { texto: q, centro: lerCentro() }));
  if (v) { await define(v); window.go("cadastro"); atualizaContagens(); }
};
async function trocaClasse(i) {
  const texto = S.cad.texto_inicial;
  const r = await edita({ classe: { id_pdm: i.id_pdm, nome: i.nome } });
  if (r && texto && !r.pedido_id) await releTexto(texto);
}

/* ------------------------------------------------------------ cadastro: tela */
function dica(c) {
  if (c.tipo === "MM") return "ex.: 16,25MM ou 15 mm";
  if (c.tipo === "POL") return 'ex.: 1.1/4POL ou 1 1/4"';
  if (c.tipo === "BAR") return "ex.: 215BAR ou 3.650 psi";
  return "";
}
const editavelAgora = v => v.estado === "RASCUNHO" && usuario().p !== "leitor";

function renderCadastro() {
  const raiz = $("#cad-raiz");
  if (!raiz) return;
  const v = S.cad;
  if (!v) { renderInicioCadastro(raiz); return; }
  // preserva o que a pessoa está digitando enquanto a resposta do servidor redesenha a tela
  const ativo = document.activeElement, foco = ativo && ativo.dataset ? ativo.dataset.foco : null;
  const digitado = foco && ativo.dataset.orig !== undefined && ativo.value !== ativo.dataset.orig ? ativo.value : null;
  const cursor = foco && ativo.selectionStart != null ? ativo.selectionStart : null;

  $("#cad-titulo").textContent = v.pedido_id ? `Pedido ${v.pedido_id}` : "Cadastrar novo item";
  legendaCadastro();
  renderAcoes(v);
  const edit = editavelAgora(v);
  limpa(raiz).append(passos(v), h("div", { class: "grid g-main" },
    h("div", {}, cartaoEstado(v), cartaoOrigem(v, edit), cartaoClasse(v, edit), v.classe ? cartaoFiscal(v, edit) : null),
    h("div", {}, cartaoDescricao(v), cartaoValidacao(v, edit), cartaoParecidos(v, edit), cartaoHistorico(v))));
  if (edit && v.classe) pintaModelo(v);
  if (S.abertoOpcoes) pintaOpcoes(S.abertoOpcoes);
  if (foco) {
    const el = raiz.querySelector(`[data-foco="${CSS.escape(foco)}"]`);
    if (el && !el.disabled) {
      if (digitado != null) el.value = digitado;
      el.focus();
      if (cursor != null && el.setSelectionRange) { try { el.setSelectionRange(cursor, cursor); } catch (e) { /* select não tem cursor */ } }
    }
  }
}
async function renderInicioCadastro(raiz) {
  $("#cad-titulo").textContent = "Cadastrar novo item";
  $("#cad-sub").textContent = "Digite o material, confirme a classe do PDM e preencha com sugestões do que já está cadastrado. A decisão final é sua.";
  limpa($("#cad-acoes"));
  const lista = h("div", { class: "cad-vazio" }, "carregando…");
  limpa(raiz).append(h("div", { class: "card", style: "margin-bottom:16px" },
    h("div", { class: "card-h" }, h("h3", {}, "O que você quer cadastrar?"), h("span", { class: "sub" }, "abreviado, no plural ou em inglês de catálogo")),
    h("div", { class: "card-b" }, campoClasse({ placeholder: "ex.: parafuso sextavado m12x50 8.8, valv esf, ball valve…", aoEscolher: comecaRascunho, aoForaDoPdm: rascunhoSemClasse }),
      h("div", { class: "faint", style: "font-size:12px;margin-top:8px" }, "Ainda não sabe se o item existe? ", h("button", { class: "cad-link", type: "button", onclick: () => window.go("busca") }, "Busque antes de cadastrar"), "."))),
  h("div", { class: "card" }, h("div", { class: "card-h" }, h("h3", {}, "Rascunhos em andamento")), h("div", { class: "card-b", style: "padding:0" }, lista)));
  const r = await tenta(() => api("GET", "/cadastros?estado=RASCUNHO&limite=50"));
  if (r) { limpa(lista); lista.className = ""; lista.append(tabelaCadastros(r.itens, "Nenhum rascunho em andamento.")); }
}
function passos(v) {
  const obrig = v.campos.filter(c => c.obrigatorio && c.aplica !== false), cheios = obrig.filter(c => c.valor).length;
  const dup = v.duplicidade, fortes = dup ? dup.candidatos.filter(c => c.nivel === "IGUAL" || c.nivel === "PROVAVEL").length : 0;
  const ncm = v.fiscal && v.fiscal.ncm.validacao;
  const passo = (ok, n, titulo, sub) => h("div", { class: `step${ok ? " done" : ""}`, style: "flex:1" }, h("div", { class: "dot" }, ok ? "✓" : n),
    h("div", {}, h("div", {}, titulo), h("div", { class: "faint", style: "font-size:11.5px" }, sub)));
  return h("div", { class: "steps-line card", style: "display:flex;gap:0;margin-bottom:16px;padding:4px 8px" },
    passo(Boolean(v.classe && v.classe.confirmada), 1, "Classe do PDM", v.classe ? (v.classe.confirmada ? "confirmada" : "falta confirmar") : "escolha a classe"),
    passo(Boolean(obrig.length) && cheios === obrig.length, 2, "Atributos", `${cheios} de ${obrig.length} obrigatórios`),
    passo(Boolean(ncm && ncm.ok), 3, "Dados fiscais e logísticos", ncm ? (ncm.ok ? "NCM vigente" : "NCM com problema") : "NCM, unidade, centro"),
    passo(!fortes && Boolean(dup), 4, "Duplicidade", !dup ? "depende da classe" : fortes ? `${fortes} ${fortes === 1 ? "possível duplicata" : "possíveis duplicatas"}` : "sem correspondência forte"),
    passo(["APROVADO", "CADASTRADO"].includes(v.estado), 5, "Aprovação", ESTADOS[v.estado] ? ESTADOS[v.estado][0] : v.estado));
}
function renderAcoes(v) {
  const box = limpa($("#cad-acoes"));
  box.append(h("span", { class: "cad-estado", id: "cad-estado", "data-estado": v.estado }, marcaEstado(v.estado)));
  box.append(h("button", { class: "btn", onclick: () => { S.cad = null; history.replaceState(null, "", "#/cadastro"); renderCadastro(); } }, "Voltar à lista"));
  if (!editavelAgora(v)) return;
  if (v.pedido_id) box.append(h("button", { class: "btn", id: "c-devolver", onclick: devolver }, "Devolver ao solicitante"));
  if (!v.classe) box.append(h("button", { class: "btn", id: "c-propor", onclick: proporClasse }, "Propor classe nova"));
  box.append(h("button", { class: "btn", id: "c-cancelar", onclick: cancelar }, "Cancelar"));
  box.append(h("button", { class: "btn danger", id: "c-recusar", onclick: recusar }, "Recusar"));
  const revisor = v.excecoes_previstas.some(e => e.exige_revisor);
  box.append(h("button", { class: "btn primary", id: "c-aprovar", disabled: v.bloqueios.length > 0, title: v.bloqueios.length ? "Resolva as pendências da validação" : "", onclick: aprovar },
    revisor ? "Enviar para revisão" : v.excecoes_previstas.length ? "Aprovar com justificativa" : "Aprovar"));
}
function aprovar() {
  const corpo = () => ({ versao: S.cad.versao, justificativas: Object.fromEntries(S.cad.excecoes_previstas.map(e => [e.id, S.just[e.id] || ""])) });
  return decisao("aprovar", corpo, r => r.estado === "EM_REVISAO" ? "Enviado para revisão de um segundo analista." : "Aprovado e enviado à fila do ERP.");
}
async function devolver() {
  const d = await dialogo({ titulo: "Devolver ao solicitante", texto: "Vazio: o sistema lista os obrigatórios que faltam.", confirmar: "Devolver",
    campos: [{ nome: "pergunta", rotulo: "Pergunta", linhas: 3, dica: "Ex.: o retentor é NBR ou FKM (Viton)?" }] });
  if (d) await decisao("devolver", { pergunta: d.pergunta || null }, r => (r.devolucao && r.devolucao.aviso) || "Devolvido ao solicitante.");
}
async function recusar() {
  const d = await dialogo({ titulo: "Recusar: fora do PDM", texto: "Encerra o cadastro. Se a classe deveria existir, use “Propor classe nova”.", confirmar: "Recusar", perigo: true,
    campos: [{ nome: "motivo", rotulo: "Motivo", linhas: 3, minimo: 5 }] });
  if (d) await decisao("recusar", { motivo: d.motivo }, "Cadastro recusado.");
}
async function cancelar() {
  const d = await dialogo({ titulo: "Cancelar este cadastro", confirmar: "Cancelar cadastro", perigo: true, campos: [{ nome: "motivo", rotulo: "Motivo (opcional)", linhas: 2 }] });
  if (d) await decisao("cancelar", { motivo: d.motivo || null }, "Cadastro cancelado.");
}
async function proporClasse() {
  const d = await dialogo({ titulo: "Propor classe nova ao PDM", texto: "O cadastro aguarda a nova versão do PDM.", confirmar: "Enviar proposta",
    campos: [{ nome: "nome_sugerido", rotulo: "Nome sugerido", minimo: 3 }, { nome: "justificativa", rotulo: "Justificativa", linhas: 3, minimo: 10 }] });
  if (d) await decisao("propor-classe", { ...d, atributos_sugeridos: [] }, "Proposta enviada ao PDM.");
}
function cartaoEstado(v) {
  const c = (classe, titulo, ...resto) => h("div", { class: `callout ${classe}`, style: "margin-bottom:16px" }, h("div", { style: "flex:1" }, h("b", { style: "font-weight:500" }, titulo), resto));
  const sub = t => h("div", { class: "muted", style: "font-size:12.5px;margin-top:3px" }, t);
  const revisor = usuario().p === "revisor";
  switch (v.estado) {
    case "JA_EXISTE": return c("ok", `Encerrado: usar o código ${v.usar_codigo}.`, v.motivo ? sub(`Justificativa: ${v.motivo}`) : null);
    case "APROVADO": return c("ok", "Aprovado. Na fila para enviar ao ERP, que gera o código.", revisor ? h("div", { style: "margin-top:8px" }, h("button", { class: "btn sm", onclick: sincronizaErp }, "Sincronizar com o ERP")) : sub("A sincronização é feita por um revisor."));
    case "CADASTRADO": return c("ok", `Cadastrado no ERP${v.codigo_erp ? ` com o código ${v.codigo_erp}` : ""}.`);
    case "ERRO_ERP": return c("warn", "O ERP recusou este envio.", v.motivo ? sub(v.motivo) : null);
    case "FORA_DO_PDM": return c("info", "Recusado: fora do PDM.", v.motivo ? sub(`Motivo: ${v.motivo}`) : null);
    case "CANCELADO": return c("info", "Cadastro cancelado.", v.motivo ? sub(`Motivo: ${v.motivo}`) : null);
    case "AGUARDANDO_REATIVACAO": return c("info", `Reativação do código ${v.usar_codigo} aprovada. Aguardando o ERP.`);
    case "AGUARDANDO_CLASSE": return c("warn", "Aguardando a nova versão do PDM.", h("div", { style: "margin-top:8px;display:flex;gap:8px" },
      h("button", { class: "btn sm", onclick: () => decisao("retomar", null, "Rascunho retomado.") }, "Retomar rascunho"),
      h("button", { class: "btn sm", onclick: recusar }, "Recusar")));
    case "AGUARDANDO_SOLICITANTE": return cartaoPergunta(v);
    case "EM_REVISAO": return c("warn", v.usar_codigo ? `Pedido de reativação do código ${v.usar_codigo}.` : "Aguardando um segundo analista.",
      S.excecoes.map(e => sub(`${nomeExcecao(e.tipo)}${e.atributo ? ` (${e.atributo})` : ""}: ${e.justificativa}`)),
      revisor ? h("div", { style: "margin-top:8px;display:flex;gap:8px" },
        h("button", { class: "btn sm primary", id: "c-rev-aprovar", onclick: () => revisa(true) }, "Aprovar exceções"),
        h("button", { class: "btn sm danger", id: "c-rev-rejeitar", onclick: () => revisa(false) }, "Rejeitar")) :
        sub("Só outra pessoa, com papel de revisor, pode decidir. Troque o usuário no topo para “bia · revisora”."));
    default: return null;
  }
}
function cartaoPergunta(v) {
  const p = S.perguntas.filter(x => !x.resposta).slice(-1)[0];
  const ta = h("textarea", { class: "inp", id: "c-resposta", placeholder: "Resposta recebida do solicitante" });
  return h("div", { class: "callout warn", style: "margin-bottom:16px" }, h("div", { style: "flex:1" },
    h("b", { style: "font-weight:500" }, "Aguardando resposta do solicitante."),
    p ? h("div", { class: "muted", style: "font-size:12.5px;margin:3px 0 8px" }, p.pergunta) : null,
    p ? h("div", {}, p.destinatario ? null : h("div", { class: "faint", style: "font-size:11.5px;margin-bottom:6px" }, "Nenhum contato cadastrado para esta área: a pergunta ficou registrada, mas nada foi enviado."), ta,
      h("button", { class: "btn sm", style: "margin-top:8px", id: "c-responder", onclick: () => { if (ta.value.trim()) decisao("responder", { pergunta_id: p.id, resposta: ta.value.trim() }, "Resposta registrada. O rascunho voltou para você."); } }, "Registrar resposta")) : null));
}
async function revisa(aprova) {
  let comentario = null;
  if (!aprova) {
    const d = await dialogo({ titulo: "Rejeitar exceções", texto: "O cadastro volta para rascunho.", confirmar: "Rejeitar", perigo: true, campos: [{ nome: "c", rotulo: "Motivo", linhas: 3, minimo: 5 }] });
    if (!d) return;
    comentario = d.c;
  }
  await decisao("revisao", { aprovar: aprova, comentario }, aprova ? "Exceções aprovadas." : "Rejeitado: voltou para rascunho.");
}
async function sincronizaErp() {
  const r = await tenta(() => api("POST", "/erp/sincronizar"));
  if (!r) return;
  avisa("Sincronização concluída.");
  if (S.cad) await abreCadastro(S.cad.id);
  atualizaContagens();
  if ($("#page-revisao").classList.contains("active")) carregaRevisao();
}
function cartaoOrigem(v, edit) {
  const p = S.pedido;
  if (v.pedido_id && p) {
    return h("div", { class: "card", style: "margin-bottom:16px" },
      h("div", { class: "card-h" }, h("h3", {}, "Origem do pedido"), h("span", { class: "sub" }, p.canal || ""),
        edit ? h("div", { class: "r" }, h("button", { class: "btn sm", id: "c-ler-ia", onclick: lerComIa }, "Completar leitura com IA")) : null),
      h("div", { class: "card-b grid g-3", style: "gap:12px" },
        h("div", {}, h("label", { class: "lbl" }, "Solicitação"), h("input", { class: "inp mono", value: p.id, readonly: true })),
        h("div", {}, h("label", { class: "lbl" }, "Área solicitante"), h("input", { class: "inp", value: p.area || "—", readonly: true })),
        h("div", {}, h("label", { class: "lbl" }, "Urgência"), h("input", { class: "inp", value: p.urgencia || "—", readonly: true })),
        h("div", { style: "grid-column:1/-1" }, h("label", { class: "lbl" }, "Texto original"), h("div", { class: "cad-texto" }, p.texto || "—")),
        p.conteudo_anexo ? h("details", { style: "grid-column:1/-1" }, h("summary", { class: "lbl" }, `Anexo: ${p.tipo_anexo || "conteúdo"}`), h("div", { class: "cad-texto" }, p.conteudo_anexo)) : null));
  }
  const ta = h("textarea", { class: "inp mono", id: "texto-origem", "data-foco": "texto", "data-orig": v.texto_inicial || "", value: v.texto_inicial || "", spellcheck: "false", disabled: !edit, placeholder: "M12X50 galvanizado 8.8 din 933…" });
  return h("div", { class: "card", style: "margin-bottom:16px" },
    h("div", { class: "card-h" }, h("h3", {}, "Texto livre"), h("span", { class: "sub" }, "opcional · preenche só o que está vazio"),
      edit && v.classe ? h("div", { class: "r" }, h("button", { class: "btn sm", id: "c-interpretar", onclick: () => {
        const t = ta.value.trim(); if (!t) return;
        releTexto(t, r => avisa(r.interpretacao.preenchidos.length ? "Preenchi: " + r.interpretacao.preenchidos.join(", ") : "Nada novo para preencher nesse texto."));
      } }, "Interpretar")) : null),
    h("div", { class: "card-b" }, ta));
}
function lerComIa() {
  avisa("Lendo o pedido com a IA…", 9000);
  return naFila(async () => {
    const r = await tenta(() => api("POST", `/cadastros/${S.cad.id}/ler-pedido`));
    if (r) { S.opcoes = {}; await define(r); avisa(r.llm && r.llm.estado === "ok" ? "Leitura concluída: só os campos vazios foram preenchidos." : "IA indisponível agora; segui só com as regras."); }
    return r;
  });
}
function cartaoClasse(v, edit) {
  const cls = v.classe, prop = v.proposta_de_classe;
  const lidos = v.campos.filter(c => c.valor && c.origem && c.origem !== "DIGITADO" && c.origem !== "OPCAO").length;
  const corpo = [];
  if (!cls) {
    corpo.push(h("div", { class: "callout warn", style: "margin-bottom:12px" }, h("div", { style: "flex:1;font-size:12.5px" }, "Nenhuma classe do PDM foi definida. O material pode estar fora do padrão: escolha uma classe, proponha uma nova ou recuse.")));
    if (prop && prop.alternativas && prop.alternativas.length) corpo.push(h("div", { class: "chip-row", style: "margin-bottom:12px" }, prop.alternativas.map(a => h("button", { class: "btn sm", onclick: () => trocaClasse({ id_pdm: a.id_pdm, nome: a.nome }) }, a.nome))));
  } else if (!cls.confirmada && edit) {
    corpo.push(h("div", { class: "callout warn", style: "margin-bottom:12px" }, h("div", { style: "flex:1;font-size:12.5px" }, "Classe proposta pela leitura do pedido. Uma pessoa precisa confirmar."),
      h("button", { class: "btn sm primary", id: "c-confirmar", onclick: () => edita({ classe: { id_pdm: cls.id_pdm, nome: cls.nome } }) }, "Confirmar classe")));
  }
  corpo.push(h("div", { class: "grid g-2", style: "gap:12px;margin-bottom:14px" },
    h("div", {}, h("label", { class: "lbl" }, "Classe PDM", h("span", { class: "req" }, "*")),
      cls ? h("input", { class: "inp", id: "cls-atual", value: `${cls.id_pdm} · ${cls.nome || "escolha o nome do material"}`, readonly: true }) : null,
      edit ? h("div", { style: cls ? "margin-top:6px" : "" }, campoClasse({ placeholder: cls ? "trocar de classe…" : "digite o material…", aoEscolher: i => trocaClasse(i) })) : null),
    cls ? h("div", {}, h("label", { class: "lbl" }, "Critério de identidade"), h("input", { class: "inp", value: cls.criterio_identidade === "REFERENCIA" ? "REFERÊNCIA DO FABRICANTE" : "ESPECIFICAÇÃO TÉCNICA", readonly: true }),
      edit && cls.nomes_possiveis.length > 1 ? h("div", { style: "margin-top:6px" }, h("select", { class: "sel", id: "c-nome", "aria-label": "Nome do material", onchange: e => edita({ classe: { id_pdm: cls.id_pdm, nome: e.target.value } }) },
        h("option", { value: "" }, "— nome do material —"), cls.nomes_possiveis.map(n => h("option", { value: n, selected: n === cls.nome }, n)))) : null) : null));
  if (cls) corpo.push(h("div", { id: "attr-form", class: "grid g-2", style: "gap:12px" }, v.campos.map(c => campoAtributo(c, edit))),
    edit ? h("div", { class: "faint", style: "font-size:11.5px;margin-top:10px" }, "Clique num campo para ver as opções mais usadas no histórico. Nada entra preenchido por frequência.") : null);
  return h("div", { class: "card", style: "margin-bottom:16px" },
    h("div", { class: "card-h" }, h("h3", {}, "Classe e atributos"), h("span", { class: "sub" }, cls ? `${cls.id_pdm} · ${cls.grupo_descricao || cls.grupo}` : ""),
      lidos ? h("div", { class: "r" }, h("span", { class: "badge b-ia" }, `${lidos} campo${lidos === 1 ? "" : "s"} lido${lidos === 1 ? "" : "s"} automaticamente`)) : null),
    h("div", { class: "card-b" }, corpo));
}
function campoAtributo(c, edit) {
  const inativo = c.aplica === false, foco = "atr:" + c.atributo, bloqueado = !edit || inativo;
  const salva = valor => edita({ valores: { [c.atributo]: valor || null } });
  let ctl;
  if (c.tipo === "LISTA") {
    ctl = h("select", { class: "sel", "data-foco": foco, "data-atr": c.atributo, disabled: bloqueado, onchange: async e => {
      if (e.target.value !== "__outro__") { salva(e.target.value); return; }
      e.target.value = c.valor || "";
      const d = await dialogo({ titulo: `${c.atributo}: valor fora da lista`, texto: "Vira exceção: exige justificativa e um segundo analista.", confirmar: "Usar este valor", campos: [{ nome: "v", rotulo: "Valor", minimo: 1 }] });
      if (d) salva(d.v);
    } },
      h("option", { value: "" }, "— selecionar —"), c.valores_permitidos.map(x => h("option", { value: x, selected: x === c.valor }, x)),
      c.valor && !c.valores_permitidos.includes(c.valor) ? h("option", { value: c.valor, selected: true }, `${c.valor} (fora do PDM)`) : null,
      edit ? h("option", { value: "__outro__" }, "Outro valor (exceção)…") : null);
  } else {
    ctl = h("input", { class: "inp mono", type: "text", "data-foco": foco, "data-orig": c.valor || "", "data-atr": c.atributo, value: c.valor || "", placeholder: dica(c), disabled: bloqueado,
      onchange: e => salva(e.target.value.trim()) });
  }
  if (edit && !inativo) ctl.addEventListener("focus", () => carregaOpcoes(c.atributo));
  const orig = c.valor && c.origem ? (ORIGENS[c.origem] || ORIGENS[c.origem.split("_")[0]] || c.origem.replaceAll("_", " ").toLowerCase()) : null;
  return h("div", { class: `cad-campo${inativo ? " inativo" : ""}${c.valido === false ? " invalido" : ""}` },
    h("label", { class: "lbl" }, c.atributo, c.obrigatorio && !inativo ? h("span", { class: "req" }, "*") : !inativo ? h("span", { class: "hint" }, "opcional") : null,
      orig ? h("span", { class: "cad-origem", title: c.trecho ? `trecho: ${c.trecho}` : "" }, orig) : null),
    ctl,
    c.valido === false ? h("div", { class: "cad-nota erro" }, "Fora do PDM: vira exceção na aprovação.") : null,
    c.aplica === null ? h("div", { class: "cad-nota" }, `Depende de outro atributo: ${c.condicao}`) : null,
    inativo ? h("div", { class: "cad-nota" }, "Não se aplica a este item.") : null,
    c.candidatos && c.candidatos.length ? h("div", { class: "cad-nota" }, "Ambíguo: " + c.candidatos.join(" · ")) : null,
    h("div", { class: "cad-opcoes", id: `op-${slug(c.atributo)}` }));
}
async function carregaOpcoes(atr) {
  S.abertoOpcoes = atr;
  if (!S.opcoes[atr]) {
    const r = await tenta(() => api("GET", `/cadastros/${S.cad.id}/sugestoes/${encodeURIComponent(atr)}`));
    if (!r) return;
    S.opcoes[atr] = r;
  }
  pintaOpcoes(atr);
}
function pintaOpcoes(atr) {
  const al = document.getElementById(`op-${slug(atr)}`), r = S.opcoes[atr];
  if (!al || !r) return;
  limpa(al);
  if (!r.opcoes.length) { al.append(h("span", { class: "cad-nota" }, r.sem_opcoes_motivo || "Sem histórico suficiente para sugerir.")); return; }
  for (const o of r.opcoes) {
    al.append(chip(`${o.valor} · ${o.n}×`, o.pct != null ? o.pct / 100 : null, () => edita({ valores: { [atr]: { valor: o.valor, origem: "OPCAO" } } })));
  }
  if (r.contexto.length) al.append(h("span", { class: "cad-nota" }, `dos itens com ${r.contexto.join(", ")} iguais`));
}
function cartaoFiscal(v, edit) {
  const f = v.fiscal, val = f.ncm.validacao, porRef = v.classe.criterio_identidade === "REFERENCIA";
  const un = f.unidade.usado || f.unidade.padrao;
  const unidades = [...new Set([f.unidade.padrao, un, ...UNIDADES].filter(Boolean))];
  const campoTexto = (rotulo, chave, valor, attrs = {}) => h("div", {}, h("label", { class: "lbl" }, rotulo),
    h("input", { class: "inp mono", type: "text", "data-foco": "campo:" + chave, "data-orig": valor || "", id: "f-" + chave, value: valor || "", disabled: !edit, onchange: e => edita({ campos: { [chave]: e.target.value.trim() || null } }), ...attrs }));
  return h("div", { class: "card", style: "margin-bottom:16px" },
    h("div", { class: "card-h" }, h("h3", {}, "Dados fiscais, logísticos e de fabricante")),
    h("div", { class: "card-b grid g-3", style: "gap:12px" },
      h("div", {}, h("label", { class: "lbl" }, "Grupo de mercadoria"), h("input", { class: "inp mono", id: "f-grupo", value: `${f.grupo.usado || f.grupo.padrao || ""} · ${v.classe.grupo_descricao || ""}`, readonly: true })),
      h("div", {}, h("label", { class: "lbl" }, "Unidade de medida", h("span", { class: "req" }, "*"), f.unidade.personalizado ? h("span", { class: "hint" }, `padrão: ${f.unidade.padrao}`) : null),
        h("select", { class: "sel", id: "f-un", disabled: !edit, onchange: e => edita({ campos: { unidade: e.target.value === f.unidade.padrao ? null : e.target.value } }) }, unidades.map(u => h("option", { value: u, selected: u === un }, u)))),
      campoTexto(h("span", {}, "NCM", h("span", { class: "req" }, "*"), " ", h("span", { class: "hint" }, f.ncm.esperado ? "sugerido pela classe" : "informe")), "ncm", f.ncm.personalizado ? f.ncm.usado : "", { placeholder: f.ncm.esperado || "0000.00.00" }),
      !porRef ? campoTexto("Fabricante", "fabricante", v.fabricante) : null,
      !porRef ? campoTexto("Referência do fabricante", "referencia_fabricante", v.referencia_fabricante, { placeholder: "part number" }) : null,
      h("div", {}, h("label", { class: "lbl" }, "Centro", h("span", { class: "req" }, "*")), selectCentro(v.centro, c => { guardaCentro(c); edita({ campos: { centro: c } }); }, { id: "f-centro", disabled: !edit || Boolean(v.pedido_id) })),
      val ? h("div", { class: `callout ${val.ok ? "ok" : "warn"}`, id: "f-ncm-nota", style: "grid-column:1/-1;font-size:12.5px" },
        h("div", {}, val.ok ? `NCM ${f.ncm.usado} vigente na tabela oficial${val.descricao ? ": " + val.descricao : ""}` :
          `NCM ${f.ncm.usado}: ${val.motivo}${val.sucessores.length ? ". Vigentes próximos: " + val.sucessores.join(", ") : ""}`)) : null),
    edit ? h("div", { id: "sugestoes-api", style: "display:none;padding:12px 16px;border-top:1px solid var(--border)" }) : null);
}
async function pintaModelo(v) {
  const box = $("#sugestoes-api"); if (!box) return;
  const chave = `${v.id}|${v.descricao.longa || ""}|${v.texto_inicial || ""}`;
  if (S.modeloChave !== chave || !S.modelo) {
    S.modeloChave = chave; S.modelo = null;
    box.style.display = ""; limpa(box).append(cabecalhoModelo(), h("div", { class: "sug-estado" }, h("span", { class: "spin", "aria-hidden": "true" }), "analisando descrição…"));
    const r = await tenta(() => api("GET", `/cadastros/${v.id}/sugestoes-modelo`));
    if (!r || S.modeloChave !== chave) return;
    S.modelo = r;
  }
  const alvo = $("#sugestoes-api"); if (!alvo) return;
  const r = S.modelo; limpa(alvo).append(cabecalhoModelo());
  if (r.estado !== "ok") { alvo.append(h("div", { class: "sug-estado" }, r.estado === "indisponivel" ? "Modelos indisponíveis agora; o cadastro segue sem eles." : "Sem texto suficiente para sugerir.")); return; }
  const atual = S.cad, porRef = atual.classe.criterio_identidade === "REFERENCIA";
  const valorRef = a => (atual.campos.find(c => c.atributo === a) || {}).valor;
  const fabAtual = porRef ? valorRef("FABRICANTE") : atual.fabricante, refAtual = porRef ? valorRef("REFERENCIA FABRICANTE") : atual.referencia_fabricante;
  const linha = (rotulo, chips) => { if (chips.length) alvo.append(h("div", { style: "display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-top:8px" }, h("span", { class: "sug-lbl" }, rotulo), chips)); };
  const relevante = s => s && (s.conf == null || +s.conf >= 0.05);
  linha("NCM", (r.ncm || []).filter(relevante).slice(0, 3).map(s => chip(s.valor_formatado || s.valor, s.conf, () => edita({ campos: { ncm: s.valor_formatado || s.valor } }), (s.valor_formatado || s.valor) === atual.fiscal.ncm.usado)));
  linha("Fabricante", ((r.fabricante || {}).sugestoes || []).filter(relevante).slice(0, 3).map(s => chip(s.valor, s.conf,
    () => edita(porRef ? { valores: { FABRICANTE: { valor: s.valor, origem: "OPCAO" } } } : { campos: { fabricante: s.valor } }), s.valor === fabAtual)));
  if (r.referencia && r.referencia.valor) linha("Referência", [chip(r.referencia.valor, r.referencia.conf,
    () => edita(porRef ? { valores: { "REFERENCIA FABRICANTE": { valor: r.referencia.valor, origem: "OPCAO" } } } : { campos: { referencia_fabricante: r.referencia.valor } }), r.referencia.valor === refAtual)]);
}
const cabecalhoModelo = () => h("div", { class: "sug-head" }, h("b", {}, "Sugestões automáticas"), h("span", { class: "ia-badge" }, "motor de sugestões"), h("span", { class: "sug-hint" }, "nada é aplicado sem o seu clique"));

function cartaoDescricao(v) {
  const copia = async () => { try { await navigator.clipboard.writeText(v.descricao.longa || ""); avisa("Descrição copiada."); } catch (e) { avisa("O navegador bloqueou a cópia."); } };
  return h("div", { class: "card", style: "margin-bottom:16px" },
    h("div", { class: "card-h" }, h("h3", {}, "Descrição gerada"), h("span", { class: "sub" }, "padrão PDM"), h("div", { class: "r" }, h("button", { class: "btn sm ghost", onclick: copia, disabled: !v.descricao.longa }, "Copiar"))),
    h("div", { class: "card-b" },
      h("label", { class: "lbl" }, "DESCRICAO_LONGA"), h("div", { class: "pdm-preview", id: "desc-long" }, v.descricao.longa || h("span", { class: "miss" }, "escolha a classe para gerar")),
      h("label", { class: "lbl", style: "margin-top:12px" }, "DESCRICAO_CURTA ", h("span", { class: "hint", id: "short-len" }, `${v.descricao.curta_tamanho}/${v.descricao.curta_limite} caracteres`)),
      h("div", { class: "pdm-preview", id: "desc-short", style: "color:var(--text)" }, v.descricao.curta || "—"),
      v.chave ? h("div", { style: "margin-top:10px" }, h("span", { class: `badge ${v.chave.completa ? "b-green" : "b-warn"}`, id: "c-chave" }, v.chave.completa ? "identidade completa" : "faltam para identificar: " + v.chave.faltando.join(", "))) : null));
}
function cartaoValidacao(v, edit) {
  const linha = (cl, ic, ...t) => h("div", { class: "check" }, h("div", { class: `ic ${cl}` }, ic), h("div", { style: "flex:1;min-width:0" }, t));
  const itens = [];
  for (const b of v.bloqueios) itens.push(linha("er", "!", frase(b.mensagem), b.sucessores && b.sucessores.length ? ` Vigentes: ${b.sucessores.join(", ")}` : ""));
  for (const a of v.avisos) itens.push(linha("wn", "?", frase(a)));
  for (const e of v.excecoes_previstas) {
    const detalhe = [e.atributo, e.padrao ? `padrão: ${e.padrao}` : null, e.usado ? `usado: ${e.usado}` : null].filter(Boolean).join(" · ");
    itens.push(linha("wn", "?", h("b", { style: "font-weight:500" }, nomeExcecao(e.tipo)), " ",
      h("span", { class: `badge ${e.exige_revisor ? "b-warn" : "b-gray"}` }, e.exige_revisor ? "exige 2º analista" : "só justificativa"),
      h("div", { class: "faint", style: "font-size:11.5px;margin:2px 0 6px" }, detalhe),
      edit ? h("textarea", { class: "inp", "data-foco": "just:" + e.id, "data-orig": S.just[e.id] || "", "data-excecao": e.id, value: S.just[e.id] || "", placeholder: "por que este item deve ser criado assim? (mín. 10 caracteres)", oninput: ev => { S.just[e.id] = ev.target.value; ev.target.dataset.orig = ev.target.value; } }) : null));
  }
  if (!itens.length && v.estado === "RASCUNHO") itens.push(linha("ok", "✓", "Sem pendências: pronto para aprovar."));
  const pend = v.bloqueios.length, exc = v.excecoes_previstas.length;
  const soma = pend ? `${pend} ${pend === 1 ? "pendência" : "pendências"}` : v.estado !== "RASCUNHO" ? "" :
    exc ? `${exc} ${exc === 1 ? "exceção" : "exceções"} a justificar` : "pronto para aprovação";
  return h("div", { class: "card", style: "margin-bottom:16px" },
    h("div", { class: "card-h" }, h("h3", {}, "Validação"), h("span", { class: "sub", id: "val-sum" }, soma)),
    h("div", { class: "card-b", id: "checks", style: "padding-top:8px;padding-bottom:8px" }, itens.length ? itens : h("div", { class: "faint", style: "font-size:12px" }, "Cadastro já decidido.")));
}
function cartaoParecidos(v, edit) {
  const dup = v.duplicidade;
  const corpo = [];
  if (!dup) corpo.push(h("div", { class: "cad-vazio" }, v.estado === "RASCUNHO" ? "Aparece depois que a classe é escolhida." : "Verificação encerrada com a decisão."));
  else {
    if (!dup.candidatos.length) corpo.push(h("div", { class: "cad-vazio" }, "Nenhum item existente coincide com o que já foi preenchido."));
    for (const c of dup.candidatos) corpo.push(cartaoCandidato(c, { acoes: edit && c.origem === "base" ? acoesCandidato(c) : null }));
    corpo.push(h("div", { class: "faint", style: "font-size:11.5px;line-height:1.5" }, `Comparado por atributos: ${numero(dup.comparaveis)} de ${numero(dup.total_classe)} itens desta classe.`,
      dup.comparaveis < dup.total_classe ? " Os demais só têm texto livre: isto não garante que o item não exista." : ""));
  }
  return h("div", { class: "card", style: "margin-bottom:16px" }, h("div", { class: "card-h" }, h("h3", {}, "Itens parecidos na base"), h("span", { class: "sub" }, "checagem de duplicidade")), h("div", { class: "card-b", id: "similar" }, corpo));
}
function acoesCandidato(c) {
  const box = h("div", { style: "margin-top:8px;display:flex;gap:8px" });
  const diverge = c.comparacao.some(x => x.estado === "diverge" && !x.opcional);
  if (c.permite_uso_direto) {
    box.append(h("button", { class: `btn sm${c.nivel === "IGUAL" ? " primary" : ""}`, "data-usar": c.codigo, onclick: async e => {
      e.stopPropagation();
      let justificativa = null;
      if (diverge) {
        const d = await dialogo({ titulo: `Usar o código ${c.codigo}`, texto: "Este item diverge em atributo de identidade.", confirmar: "Usar este código", campos: [{ nome: "j", rotulo: "Justificativa", linhas: 3, minimo: 10, dica: "Ex.: aplicação aceita folga normal; confirmado com PCM." }] });
        if (!d) return;
        justificativa = d.j;
      }
      decisao("usar-existente", { codigo: c.codigo, justificativa }, `Registrado: usar o código ${c.codigo}.`);
    } }, "Usar este código"));
  } else {
    box.append(h("button", { class: "btn sm", "data-reativar": c.codigo, onclick: async e => {
      e.stopPropagation();
      const d = await dialogo({ titulo: `Pedir reativação de ${c.codigo}`, texto: `O código está ${c.status}. Um segundo analista decide.`, confirmar: "Pedir reativação", campos: [{ nome: "j", rotulo: "Justificativa", linhas: 3, minimo: 10 }] });
      if (d) decisao("reativar", { codigo: c.codigo, justificativa: d.j }, "Reativação enviada ao segundo analista.");
    } }, "Pedir reativação"));
  }
  return box;
}
function cartaoHistorico(v) {
  const det = h("details", { class: "card", open: Boolean(S.historico) },
    h("summary", { class: "cad-resumo" }, "Histórico e auditoria"),
    h("div", { class: "card-b", style: "padding-top:0" }, (S.historico || []).map(e =>
      h("div", { class: "cad-evento" }, h("span", { class: "mono" }, String(e.quando || e.criado_em || e.em || "").slice(0, 16).replace("T", " ")), " ", h("b", { style: "font-weight:500" }, e.autor), " ", (e.acao || "").replaceAll("_", " ")))));
  det.addEventListener("toggle", async () => {
    if (det.open && !S.historico) { S.historico = (await tenta(() => api("GET", `/cadastros/${v.id}/historico`))) || []; renderCadastro(); }
    if (!det.open) S.historico = null;
  });
  return det;
}

/* ------------------------------------------------------------ pedidos */
async function carregaPedidos() {
  const box = $("#ped-tabela");
  const par = new URLSearchParams({ limite: P.limite, offset: P.offset });
  if (P.estado) par.set("estado", P.estado);
  if (P.urgencia) par.set("urgencia", P.urgencia);
  if (P.q) par.set("q", P.q);
  const [r, resumo] = await Promise.all([tenta(() => api("GET", "/pedidos?" + par)), atualizaContagens()]);
  if (!r) return;
  if (resumo) {
    const kpi = (l, v, s) => h("div", { class: "card kpi" }, h("div", { class: "l" }, l), h("div", { class: "v" }, numero(v)), h("div", { class: "s" }, s));
    const pd = resumo.pedidos, total = Object.values(pd).reduce((a, b) => a + b, 0);
    limpa($("#ped-kpis")).append(kpi("Pedidos novos", pd.NOVO || 0, `de ${numero(total)} recebidos`), kpi("Em andamento", pd.EM_ANDAMENTO || 0, "com um analista"),
      kpi("Devolvidos", pd.DEVOLVIDO || 0, "aguardando o solicitante"), kpi("Encerrados", total - (pd.NOVO || 0) - (pd.EM_ANDAMENTO || 0) - (pd.DEVOLVIDO || 0), "aprovados, já existentes ou recusados"));
  }
  $("#ped-total").textContent = `${numero(r.total)} pedido${r.total === 1 ? "" : "s"}`;
  limpa(box);
  if (!r.itens.length) { box.append(h("div", { class: "cad-vazio" }, "Nenhum pedido com estes filtros.")); limpa($("#ped-pager")); return; }
  const corUrg = u => u === "EMERGENCIAL" ? "b-err" : u === "ALTA" ? "b-warn" : "b-gray";
  box.append(h("table", { class: "tbl" },
    h("thead", {}, h("tr", {}, ["SOLICITAÇÃO", "DATA", "ÁREA", "URGÊNCIA", "TEXTO DO PEDIDO", "ESTADO", ""].map(t => h("th", {}, t)))),
    h("tbody", {}, r.itens.map(p => h("tr", { "data-pedido": p.id },
      h("td", { class: "mono" }, p.id), h("td", { class: "mono" }, (p.data_solicitacao || "").slice(0, 10)), h("td", {}, p.area || "—"),
      h("td", {}, h("span", { class: `badge ${corUrg(p.urgencia)}` }, p.urgencia || "—"), p.tem_anexo ? h("span", { class: "badge b-info", style: "margin-left:4px" }, "anexo") : null),
      h("td", { class: "wrap", title: p.texto || "" }, trunca(p.texto, 110)),
      h("td", {}, marcaEstado(p.estado), p.analista ? h("span", { class: "faint", style: "margin-left:6px" }, p.analista) : null),
      h("td", {}, h("button", { class: `btn sm${p.estado === "NOVO" ? " primary" : ""}`, onclick: () => abrePedido(p) }, p.estado === "NOVO" ? "Assumir" : "Abrir")))))));
  const pg = limpa($("#ped-pager")), fim = Math.min(P.offset + P.limite, r.total);
  pg.append(h("span", { class: "faint" }, `${numero(P.offset + 1)}–${numero(fim)} de ${numero(r.total)}`),
    h("button", { class: "btn sm", disabled: P.offset === 0, onclick: () => { P.offset = Math.max(0, P.offset - P.limite); carregaPedidos(); } }, "Anterior"),
    h("button", { class: "btn sm", disabled: fim >= r.total, onclick: () => { P.offset += P.limite; carregaPedidos(); } }, "Próxima"));
}
async function abrePedido(p) {
  if (p.estado === "NOVO") {
    const v = await tenta(() => api("POST", `/pedidos/${p.id}/assumir`));
    if (v) { await define(v); window.go("cadastro"); atualizaContagens(); }
    return;
  }
  const r = await tenta(() => api("GET", `/cadastros?pedido_id=${encodeURIComponent(p.id)}&limite=1`));
  if (r && r.itens[0]) abreCadastro(r.itens[0].id);
  else avisa("Este pedido não tem cadastro associado.");
}

/* ------------------------------------------------------------ acompanhamento e revisão */
function tabelaCadastros(itens, vazio) {
  if (!itens.length) return h("div", { class: "cad-vazio" }, vazio);
  return h("table", { class: "tbl" },
    h("thead", {}, h("tr", {}, ["MATERIAL", "PEDIDO", "CLASSE", "ESTADO", "RESPONSÁVEL", "ATUALIZADO", ""].map(t => h("th", {}, t)))),
    h("tbody", {}, itens.map(c => h("tr", { "data-cadastro": c.id },
      h("td", { class: "wrap" }, c.descricao_curta || c.nome || "sem classe"), h("td", { class: "mono" }, c.pedido_id || "—"), h("td", { class: "mono" }, c.id_pdm || "—"),
      h("td", {}, marcaEstado(c.estado)), h("td", {}, c.analista || "—"), h("td", { class: "mono" }, String(c.atualizado_em || "").slice(0, 16).replace("T", " ")),
      h("td", {}, h("button", { class: "btn sm", onclick: () => abreCadastro(c.id) }, "Abrir"))))));
}
async function carregaCadastros() {
  const par = new URLSearchParams({ limite: 100 });
  if (L.estado) par.set("estado", L.estado);
  if (L.analista) par.set("analista", L.analista);
  const [r] = await Promise.all([tenta(() => api("GET", "/cadastros?" + par)), atualizaContagens()]);
  if (!r) return;
  $("#cads-total").textContent = `${numero(r.total)} cadastro${r.total === 1 ? "" : "s"}`;
  limpa($("#cads-tabela")).append(tabelaCadastros(r.itens, "Nenhum cadastro com estes filtros."));
}
async function carregaRevisao() {
  atualizaContagens();
  const box = limpa($("#rev-tabela")), erp = limpa($("#rev-erp"));
  const papel = usuario().p;
  if (papel !== "revisor") {
    box.append(h("div", { class: "cad-vazio" }, "Só quem tem papel de revisor decide exceções. Troque o usuário no topo para “bia · revisora”."));
  } else {
    const ex = await tenta(() => api("GET", "/excecoes"));
    if (ex) {
      const porCad = new Map();
      for (const e of ex) { if (!porCad.has(e.cadastro_id)) porCad.set(e.cadastro_id, []); porCad.get(e.cadastro_id).push(e); }
      if (!porCad.size) box.append(h("div", { class: "cad-vazio" }, "Nenhuma exceção aguardando decisão."));
      else box.append(h("table", { class: "tbl" },
        h("thead", {}, h("tr", {}, ["MATERIAL", "PEDIDO", "EXCEÇÃO", "JUSTIFICATIVA", "AUTOR", ""].map(t => h("th", {}, t)))),
        h("tbody", {}, [...porCad.entries()].map(([id, lista]) => h("tr", { "data-cadastro": id },
          h("td", {}, lista[0].nome || "—"), h("td", { class: "mono" }, lista[0].pedido_id || "—"),
          h("td", { class: "wrap" }, lista.map(e => nomeExcecao(e.tipo) + (e.atributo ? ` (${e.atributo})` : "")).join("; ")),
          h("td", { class: "wrap" }, trunca(lista.map(e => e.justificativa).join(" · "), 120)), h("td", {}, lista[0].autor),
          h("td", {}, h("button", { class: "btn sm primary", onclick: () => abreCadastro(id) }, "Decidir")))))));
    }
  }
  $("#rev-sync").style.display = papel === "revisor" ? "" : "none";
  if (papel === "leitor") { erp.append(h("div", { class: "cad-vazio" }, "Sem permissão para ver os envios.")); return; }
  const envios = await tenta(() => api("GET", "/erp/envios"));
  if (!envios) return;
  if (!envios.length) { erp.append(h("div", { class: "cad-vazio" }, "Nenhum envio ao ERP ainda.")); return; }
  erp.append(h("table", { class: "tbl" },
    h("thead", {}, h("tr", {}, ["TIPO", "ESTADO", "TENTATIVAS", "PROTOCOLO", "ATUALIZADO", ""].map(t => h("th", {}, t)))),
    h("tbody", {}, envios.map(e => h("tr", {}, h("td", {}, e.tipo), h("td", {}, marcaEstado(e.estado)), h("td", { class: "num" }, e.tentativas), h("td", { class: "mono" }, e.protocolo || "—"),
      h("td", { class: "mono" }, String(e.atualizado_em || "").slice(0, 16).replace("T", " ")), h("td", {}, h("button", { class: "btn sm", onclick: () => abreCadastro(e.cadastro_id) }, "Abrir")))))));
}

/* ------------------------------------------------------------ material da base */
async function abreMaterial(codigo) {
  const r = await tenta(() => api("GET", `/materiais/${encodeURIComponent(codigo)}`));
  if (!r) return;
  const m = r.material, k = r.classificacao, corpo = limpa($("#mat-corpo"));
  $("#mat-titulo").textContent = m.codigo;
  corpo.append(
    h("div", { style: "display:flex;gap:8px;align-items:center;margin-bottom:10px" }, marcaEstado2(m.status), h("span", { class: "badge b-gray" }, m.grupo || "—")),
    h("div", { class: "pdm-preview", style: "margin-bottom:14px" }, m.descricao_longa || m.descricao_curta || "—"),
    h("table", { class: "tbl", style: "margin-bottom:14px" }, h("tbody", {}, [["Centro", m.centro], ["Estoque", `${numero(m.estoque)} ${m.unidade || ""}`], ["NCM", m.ncm], ["Fabricante", m.fabricante], ["Referência", m.referencia_fabricante],
      ["Classe lida", k ? `${k.id_pdm} · ${k.nome || ""}` : "não classificado"]].map(([a, b]) => h("tr", {}, h("td", { class: "muted" }, a), h("td", { class: "wrap" }, b || "—"))))),
    r.atributos.length ? h("div", {}, h("div", { class: "lbl" }, "Atributos lidos"), h("div", { class: "chip-row" }, r.atributos.map(a => h("span", { class: "chip", title: a.trecho || "" }, `${a.atributo}: ${a.valor}`)))) : null);
  $("#ov-mat").classList.add("open"); $("#drawer-mat").classList.add("open");
}
function fechaMaterial() { $("#ov-mat").classList.remove("open"); $("#drawer-mat").classList.remove("open"); }

/* ------------------------------------------------------------ partida */
function ligaFiltros() {
  $("#q").addEventListener("input", buscaAdiada);
  $("#q").addEventListener("keydown", e => { if (e.key === "Enter") buscaAgora(); });
  $("#b-buscar").addEventListener("click", buscaAgora);
  $("#b-limpar").addEventListener("click", limpaBusca);
  const pedidos = debounce(() => { P.offset = 0; carregaPedidos(); }, 250);
  $("#ped-estado").addEventListener("change", e => { P.estado = e.target.value; pedidos(); });
  $("#ped-urg").addEventListener("change", e => { P.urgencia = e.target.value; pedidos(); });
  $("#ped-q").addEventListener("input", e => { P.q = e.target.value.trim(); pedidos(); });
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
    if (S.cad) abreCadastro(S.cad.id);
    else { const ativa = $(".page.active"); if (ativa) window.go(ativa.id.replace("page-", "")); }
  });
  window.addEventListener("hashchange", rota);
}
async function inicia() {
  try { const salvo = localStorage.getItem("cadastro-usuario"); if (salvo) $("#usuario").value = salvo; } catch (e) { /* preferência local, opcional */ }
  $("#avatar").textContent = usuario().u.slice(0, 2).toUpperCase();
  ligaFiltros(); pintaBusca();
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
