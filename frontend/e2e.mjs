/* Teste de ponta a ponta do cadastro no frontend, em um Chrome de verdade, clicando como uma pessoa.
 * O cadastro é o painel (backend/app/painel/index.html) embutido em #page-cadastro.
 * GRAVA DADOS E AUDITORIA (imutável): rode só contra um banco descartável, nunca contra o de uso.
 *
 *   google-chrome --headless=new --remote-debugging-port=9223 --user-data-dir=/tmp/perfil about:blank &
 *   node frontend/e2e.mjs http://localhost:8001 /pasta/das/capturas
 */
import fs from "node:fs";

const BASE = process.argv[2] || "http://localhost:8001", PASTA = process.argv[3] || ".", PORTA = process.env.CDP_PORTA || 9223;
const lista = await (await fetch(`http://localhost:${PORTA}/json`)).json();
const ws = new WebSocket(lista.find(t => t.type === "page").webSocketDebuggerUrl);
await new Promise(r => ws.addEventListener("open", r));
let id = 0, falhas = 0, passos = 0;
const pend = new Map(), erros = [], http = [], respostas = [];
const cdp = (method, params = {}) => new Promise(r => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
ws.addEventListener("message", e => {
  const m = JSON.parse(e.data);
  if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); }
  if (m.method === "Runtime.exceptionThrown") erros.push(m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text);
  if (m.method === "Network.responseReceived" && m.params.response.status >= 500) http.push(`${m.params.response.status} ${m.params.response.url}`);
  if (m.method === "Page.javascriptDialogOpening") cdp("Page.handleJavaScriptDialog", { accept: true, promptText: respostas.shift() ?? "" });
});
const ev = async expr => {
  const r = await cdp("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true });
  if (r.result.exceptionDetails) throw new Error(`${expr.slice(0, 110)} -> ${r.result.exceptionDetails.exception?.description}`);
  return r.result.result.value;
};
const pausa = ms => new Promise(r => setTimeout(r, ms));
const J = JSON.stringify;
const D = "document.querySelector('#painel').contentDocument";      // documento do painel
const W = "document.querySelector('#painel').contentWindow";
const em = s => `${D}.querySelector(${J(s)})`;
async function espera(expr, ms = 9000) {
  const fim = Date.now() + ms;
  while (Date.now() < fim) { if (await ev(`(()=>{try{return Boolean(${expr})}catch(e){return false}})()`)) return true; await pausa(120); }
  return false;
}
const ok = async (nome, cond, det = "") => {
  passos++; if (!cond) falhas++;
  console.log(`${cond ? "OK   " : "FALHA"} ${nome}${det ? "  -> " + String(det).replace(/\n/g, " ").slice(0, 170) : ""}`);
  if (!cond) console.log("      aviso do painel:", await ev(`${em("#toast")}.textContent`), "| estado:", await estado());
};
const estado = () => ev(`${W}.eval("S.cad ? S.cad.estado : ''")`);
const esperaEstado = e => espera(`${W}.eval("S.cad && S.cad.estado")===${J(e)}`);
const clica = sel => ev(`(()=>{const e=${em(sel)};if(!e)throw new Error('sem '+${J(sel)});e.click()})()`);
const clicaTexto = (sel, txt) => ev(`(()=>{const e=[...${D}.querySelectorAll(${J(sel)})].find(x=>!x.disabled&&x.textContent.includes(${J(txt)}));if(!e)throw new Error('sem '+${J(txt)});e.click()})()`);
const preenche = (sel, v) => ev(`(()=>{const e=${em(sel)};e.focus();e.value=${J(v)};e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}))})()`);
const texto = sel => ev(`(${em(sel)}||{}).innerText||''`);
const valor = sel => ev(`(${em(sel)}||{}).value||''`);
const existe = sel => ev(`Boolean(${em(sel)})`);
const shot = async nome => { const r = await cdp("Page.captureScreenshot", {}); fs.writeFileSync(`${PASTA}/${nome}.png`, Buffer.from(r.result.data, "base64")); };
const menu = async p => { await ev(`document.querySelector('.side-item[data-nav="${p}"]').click()`); await pausa(350); };
const usuario = async v => { await ev(`(()=>{const s=document.querySelector('#usuario');s.value=${J(v)};s.dispatchEvent(new Event('change',{bubbles:true}))})()`); await pausa(500); };

await cdp("Runtime.enable"); await cdp("Page.enable"); await cdp("Network.enable");
await cdp("Emulation.setFocusEmulationEnabled", { enabled: true });
await cdp("Emulation.setDeviceMetricsOverride", { width: 1560, height: 1100, deviceScaleFactor: 1, mobile: false });
await cdp("Page.navigate", { url: BASE + "/" });
await espera(`${W}.painel`);
await usuario("ana|analista");

console.log("\n== o painel dentro do frontend");
await menu("cadastro");
await ok("cadastrar abre o painel dentro do frontend", await ev(`document.querySelector('#page-cadastro').classList.contains('active')`));
await ok("o menu do frontend continua à vista", await ev(`document.querySelector('.side').offsetParent!==null`));
await ok("o cabeçalho duplicado some", await ev(`getComputedStyle(${em("header")}).display==='none'`));
await ok("três colunas lado a lado", await ev(`(()=>{const a=${em("#col-esq")}.getBoundingClientRect(),b=${em("#col-meio")}.getBoundingClientRect(),c=${em("#col-dir")}.getBoundingClientRect();return a.right<=b.left&&b.right<=c.left})()`));
await ok("o painel recebe o usuário do topo", (await ev(`${em("#usuario")}.value`)) === "ana|analista");

console.log("\n== fluxo do painel: digitar, escolher, preencher");
await preenche("#q", "rolamento rig");
await ok("digitar sugere as classes", await espera(`${em("#resultado-nomes .item")}`), await texto("#resultado-nomes"));
await clica("#resultado-nomes .item");
await ok("clicar na classe abre o rascunho", await esperaEstado("RASCUNHO"), await texto("#cadastro h2"));
await preenche('[data-atr="REFERENCIA"]', "SKF 6205-2RSH/C3");
await ok("a tabela técnica completa as medidas", await espera(`${em('[data-atr="DIAMETRO EXTERNO"]')}.value==='52MM'`));
await ok("duplicados aparecem ao lado do formulário", await espera(`${em("#lateral .cand")}`));
await ok("sugestões do modelo aparecem", await espera(`${em("#cadastro .chip")}`));
await ok("nenhuma sugestão entra sozinha", await ev(`${W}.eval("S.cad.fabricante")===null`));
await ev(`${em('[data-atr="VEDACAO"]')}.focus()`);
await ok("opções do histórico ao focar o campo", await espera(`${em("#sug-VEDACAO .chip")}`), await texto("#sug-VEDACAO"));
await clica("#sug-VEDACAO .chip");
await ok("clicar na opção preenche", await espera(`${em('[data-atr="VEDACAO"]')}.value!==''`), await valor('[data-atr="VEDACAO"]'));
await preenche('[data-atr="FOLGA"]', "C3");
await ok("a descrição é gerada", await espera(`${em("#lateral .desc")}.innerText.includes('FOLGA: C3')`), await texto("#lateral .desc"));
await shot("1_cadastro");

console.log("\n== exceção, justificativa e segunda pessoa");
await ok("duplicidade vira exceção com justificativa", await espera(`${em("#lateral textarea")}`), await ev(`[...${D}.querySelectorAll('#lateral h2')].map(e=>e.innerText).join(' | ')`));
await ev(`${D}.querySelectorAll('#lateral textarea').forEach(t=>{t.value='item novo confirmado com o PCM';t.dispatchEvent(new Event('input',{bubbles:true}))})`);
// editar e aprovar quase juntos, com duplo clique: a aprovação espera a edição e não vira conflito falso
await ev(`(()=>{const e=${em('[data-atr="REFERENCIA"]')};e.value='6205-2RS/C3';e.dispatchEvent(new Event('change',{bubbles:true}));const b=[...${D}.querySelectorAll('#lateral button')].find(x=>x.textContent.startsWith('Aprovar'));b.click();b.click()})()`);
await ok("editar e aprovar juntos não acusa conflito falso", await espera(`${W}.eval("S.cad.estado")!=='RASCUNHO'`), await estado());
await pausa(400);
await ok("duplo clique não gera erro", !(await texto("#toast")).includes("não permitida"), await texto("#toast"));
await ok("foi para revisão", (await estado()) === "EM_REVISAO", await estado());
const cid = await ev(`${W}.eval("S.cad.id")`);
await usuario("bia|revisor");
await menu("revisao");
await ok("a revisão lista o cadastro", await espera(`document.querySelector('#rev-tabela tr[data-cadastro]')`), await ev(`document.querySelector('#rev-tabela').innerText`));
await ev(`document.querySelector('#rev-tabela button').click()`);
await ok("decidir abre o cadastro no painel", await espera(`document.querySelector('#page-cadastro').classList.contains('active')&&${W}.eval("S.cad&&S.cad.id")===${J(cid)}`));
await espera(`[...${D}.querySelectorAll('#lateral button')].some(b=>b.textContent==='Aprovar exceções')`);
await clicaTexto("#lateral button", "Aprovar exceções");
await ok("a segunda pessoa aprova", await esperaEstado("APROVADO"));
await usuario("ana|analista");
await shot("2_aprovado");

console.log("\n== pedidos");
await menu("pedidos");
await ok("pedidos abre a aba do painel", await espera(`${em("#lista-pedidos .item")}`), await ev(`${em("#lista-pedidos")}.innerText.slice(0,60)`));
await ok("o menu marca Pedidos", await ev(`document.querySelector('.side-item[data-nav="pedidos"]').classList.contains('active')`));
await clica("#lista-pedidos .item");
await ok("assumir abre o rascunho do pedido", await espera(`${W}.eval("S.cad&&S.cad.pedido_id")`), await ev(`${W}.eval("S.cad.pedido_id")`));
await ok("o texto do pedido fica à vista", (await texto("#cadastro .texto-pedido")).length > 5, await texto("#cadastro .texto-pedido"));
if (await espera(`[...${D}.querySelectorAll('#cadastro button')].some(b=>b.textContent==='Confirmar classe')`, 1500)) {
  await clicaTexto("#cadastro button", "Confirmar classe");
  await ok("a pessoa confirma a classe", await espera(`![...${D}.querySelectorAll('#cadastro button')].some(b=>b.textContent==='Confirmar classe')`));
}
await shot("3_pedido");

console.log("\n== usar código existente e recusar");
await menu("busca");
await preenche("#q", "rolamento rig");
await espera(`${em("#resultado-nomes .item")}`);
await clica("#resultado-nomes .item");
await esperaEstado("RASCUNHO");
await espera(`${W}.eval("S.cad.pedido_id")===null`);
await preenche('[data-atr="REFERENCIA"]', "6205-2RS/C3");
await ok("candidatos oferecem usar o código", await espera(`[...${D}.querySelectorAll('#lateral button')].some(b=>b.textContent==='Usar este código')`));
await ev(`(()=>{const b=[...${D}.querySelectorAll('#lateral button')].find(x=>x.textContent==='Usar este código');b.click();b.click()})()`);   // duplo clique
await ok("usar encerra como já existe", await esperaEstado("JA_EXISTE"), await ev(`${W}.eval("S.cad.usar_codigo")`));
await pausa(300);
await ok("duplo clique em usar não gera erro", !(await texto("#toast")).includes("não permitida"), await texto("#toast"));
await preenche("#q", "rolamento rig");
await espera(`${em("#resultado-nomes .item")}`);
await clica("#resultado-nomes .item");
await espera(`${W}.eval("S.cad.estado")==='RASCUNHO'`);
respostas.push("mobiliário não é material de manutenção");
await espera(`[...${D}.querySelectorAll('#lateral button')].some(b=>b.textContent==='Recusar')`);
await clicaTexto("#lateral button", "Recusar");
await ok("recusar usa o motivo digitado", await esperaEstado("FORA_DO_PDM"));

console.log("\n== cadastros, permissões e tema");
await menu("cadastros");
await ok("a lista mostra os cadastros", await espera(`document.querySelector('#cads-tabela tr[data-cadastro]')`), await ev(`document.querySelector('#cads-total').innerText`));
await ev(`document.querySelector('#cads-tabela tr[data-cadastro] button').click()`);
await ok("abrir leva ao painel", await espera(`document.querySelector('#page-cadastro').classList.contains('active')`));
await usuario("leo|leitor");
await menu("cadastro");
await preenche("#q", "valvula esfera");
await espera(`${em("#resultado-nomes .item")}`);
await clica("#resultado-nomes .item");
await ok("leitor recebe recusa do servidor", await espera(`${em("#toast")}.textContent.length>0&&!${em("#toast")}.hidden`), await texto("#toast"));
await usuario("ana|analista");
const antes = await ev(`${em("html")}.dataset.tema`);
await ev(`document.querySelector('.theme-btn').click()`); await pausa(300);
await ok("o tema acompanha o frontend", (await ev(`${em("html")}.dataset.tema`)) !== antes, await ev(`${em("html")}.dataset.tema`));
await shot("4_outro_tema");
await cdp("Page.reload"); await pausa(1500);
await espera(`${W}.painel`);
await ok("recarregar mantém a tela", await ev(`document.querySelector('.page.active')!==null`), await ev(`document.querySelector('.page.active').id`));

console.log("\n== telas do time continuam de pé");
for (const p of ["base", "clusters", "requisicoes", "radar", "inicio"]) {
  await ev(`go(${J(p)})`); await pausa(250);
  await ok(`tela ${p}`, await ev(`document.querySelector('#page-${p}').classList.contains('active')&&document.querySelector('#page-${p}').innerText.length>50`));
}

console.log(`\n${passos - falhas} de ${passos} passaram`);
console.log("erros de JavaScript:", erros.length ? erros.slice(0, 4) : "nenhum");
console.log("respostas 5xx:", http.length ? http.slice(0, 4) : "nenhuma");
ws.close();
process.exit(falhas || erros.length || http.length ? 1 : 0);
