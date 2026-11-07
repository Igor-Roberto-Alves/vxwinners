/* Teste de ponta a ponta do cadastro no frontend, em um Chrome de verdade, clicando como uma pessoa.
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
const pend = new Map(), erros = [], http = [], trilha = [];
ws.addEventListener("message", e => {
  const m = JSON.parse(e.data);
  if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); }
  if (m.method === "Runtime.exceptionThrown") erros.push(m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text);
  if (m.method === "Network.responseReceived" && m.params.response.status >= 500) http.push(`${m.params.response.status} ${m.params.response.url}`);
  if (m.method === "Network.requestWillBeSent" && m.params.request.method !== "GET") trilha.push(`${new Date().toISOString().slice(17, 23)} -> ${m.params.request.method} ${m.params.request.url.split("/").slice(-1)[0].slice(0, 14)} ${(m.params.request.postData || "").slice(0, 70)}`);
  if (m.method === "Network.responseReceived" && m.params.response.url.includes("/api/v1/cadastros") && m.params.response.status >= 400) trilha.push(`${new Date().toISOString().slice(17, 23)} <- ${m.params.response.status}`);
});
const cdp = (method, params = {}) => new Promise(r => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async expr => {
  const r = await cdp("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true });
  if (r.result.exceptionDetails) throw new Error(`${expr.slice(0, 90)} -> ${r.result.exceptionDetails.exception?.description}`);
  return r.result.result.value;
};
const pausa = ms => new Promise(r => setTimeout(r, ms));
async function espera(expr, ms = 9000) {
  const fim = Date.now() + ms;
  while (Date.now() < fim) { if (await ev(`Boolean(${expr})`)) return true; await pausa(120); }
  return false;
}
const ok = async (nome, cond, det = "") => {
  passos++; if (!cond) falhas++;
  console.log(`${cond ? "OK   " : "FALHA"} ${nome}${det ? "  -> " + String(det).slice(0, 170) : ""}`);
  if (!cond) {
    console.log(trilha.slice(-6).map(x => "      " + x).join("\n"));
    console.log("      aviso na tela:", await ev(`document.querySelector('#toast-t').innerText`), "| página:", await ev(`document.querySelector('.page.active').id`), "| estado:", await ev(`(document.querySelector('#cad-estado')||{dataset:{}}).dataset.estado||'-'`));
  }
};
const clica = sel => ev(`(()=>{const e=document.querySelector(${JSON.stringify(sel)});if(!e)throw new Error('sem elemento '+${JSON.stringify(sel)});e.click()})()`);
const clicaTexto = (tag, txt) => ev(`(()=>{const e=[...document.querySelectorAll(${JSON.stringify(tag)})].find(x=>x.offsetParent&&x.innerText.includes(${JSON.stringify(txt)}));if(!e)throw new Error('sem '+${JSON.stringify(txt)});e.click()})()`);
const preenche = (sel, v) => ev(`(()=>{const e=document.querySelector(${JSON.stringify(sel)});e.focus();e.value=${JSON.stringify(v)};e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}))})()`);
const texto = sel => ev(`(document.querySelector(${JSON.stringify(sel)})||{}).innerText||''`);
const valor = sel => ev(`(document.querySelector(${JSON.stringify(sel)})||{}).value||''`);
const existe = sel => ev(`Boolean(document.querySelector(${JSON.stringify(sel)}))`);
const estado = () => ev(`(document.querySelector('#cad-estado')||{dataset:{}}).dataset.estado||''`);
const esperaEstado = e => espera(`(document.querySelector('#cad-estado')||{dataset:{}}).dataset.estado===${JSON.stringify(e)}`);
const shot = async nome => { const r = await cdp("Page.captureScreenshot", {}); fs.writeFileSync(`${PASTA}/${nome}.png`, Buffer.from(r.result.data, "base64")); };
const usuario = async v => { await ev(`(()=>{const s=document.querySelector('#usuario');s.value=${JSON.stringify(v)};s.dispatchEvent(new Event('change',{bubbles:true}))})()`); await pausa(500); };
const menu = async p => { await clica(`.side-item[data-nav="${p}"]`); await pausa(300); };
const dialogoPreenche = async (...valores) => {
  await espera(`document.querySelector('.cad-dlg')`);
  for (let i = 0; i < valores.length; i++) await ev(`(()=>{const e=document.querySelectorAll('.cad-dlg .inp')[${i}];e.value=${JSON.stringify(valores[i])}})()`);
};
const dialogoConfirma = () => ev(`document.querySelector('.cad-dlg-acoes .btn:last-child').click()`);

await cdp("Runtime.enable"); await cdp("Page.enable"); await cdp("Network.enable");
await cdp("Emulation.setFocusEmulationEnabled", { enabled: true });  // sem janela, o Chrome não dispara eventos de foco
await cdp("Emulation.setDeviceMetricsOverride", { width: 1560, height: 1200, deviceScaleFactor: 1, mobile: false });
await cdp("Page.navigate", { url: BASE + "/" });
await espera(`document.querySelector('#n-pedidos')&&document.querySelector('#n-pedidos').innerText!=='—'`);

await usuario("ana|analista");   // o navegador lembra o último usuário
console.log("\n== abertura");
await ok("menu mostra a fila real de pedidos", (await texto("#n-pedidos")) !== "—", await texto("#n-pedidos"));
await ok("status da API visível", (await texto("#api-status")).includes("API ok"), await texto("#api-status"));
await ok("tela de demonstração avisa que os dados são fictícios", (await texto("#pill-dados")).includes("fictícios"));

console.log("\n== busca antes de cadastrar");
await menu("busca");
await ok("a busca avisa que os dados são reais", (await texto("#pill-dados")).includes("dados reais"));
await preenche("#q", "parafuso sextavado m12x50 8.8 aco carbono zincado din 933");
await ok("candidatos aparecem", await espera(`document.querySelector('#cands .cand')`));
await ok("classe proposta pela leitura, não decidida", (await texto("[data-classe]")).includes("proposta"), await texto("[data-classe]"));
const lido = await texto("#b-leitura");
await ok("texto interpretado", lido.includes("BITOLA: M12") && lido.includes("COMPRIMENTO: 50MM"), lido.replace(/\n/g, " "));
await ok("comparação atributo a atributo", await existe("#cands .attr.eq"));
await shot("1_busca");
await clica("#cands .cand");
await ok("escolher candidato preenche a decisão", /^\d+$/.test(await texto("#picked-code")), await texto("#picked-code"));
await clica("#b-novo");
await ok("cadastrar novo abre o rascunho", await esperaEstado("RASCUNHO"));

console.log("\n== rascunho nascido da busca");
await ok("o que foi lido veio junto", (await valor('[data-atr="BITOLA"]')) === "M12" && (await valor('[data-atr="COMPRIMENTO"]')) === "50MM");
await ok("classe já confirmada pela pessoa", !(await existe("#c-confirmar")));
await ok("descrição gerada pelo servidor", (await texto("#desc-long")).startsWith("PARAFUSO SEXTAVADO"), await texto("#desc-long"));
await ok("duplicidade ao vivo", await espera(`document.querySelector('#similar .cand')`));
await ok("sugestões do modelo aparecem", await espera(`document.querySelector('#sugestoes-api .conf-chip')`), (await texto("#sugestoes-api")).replace(/\n/g, " "));
const longaAntes = await texto("#desc-long");
await preenche('[data-atr="ACABAMENTO"]', "");
await ok("remover um valor recalcula a descrição", await espera(`document.querySelector('#desc-long').innerText!==${JSON.stringify(longaAntes)}`));
await ev(`document.querySelector('[data-atr="ACABAMENTO"]').focus()`);
await ok("opções do histórico ao focar o campo", await espera(`document.querySelector('#op-ACABAMENTO .conf-chip')`), (await texto("#op-ACABAMENTO")).replace(/\n/g, " "));
await ok("valor vazio bloqueia a aprovação", await ev(`document.querySelector('#c-aprovar').disabled`), (await texto("#checks")).replace(/\n/g, " "));
await clica("#op-ACABAMENTO .conf-chip");
await ok("clicar na opção aplica e marca a origem", await espera(`document.querySelector('[data-atr="ACABAMENTO"]').value!=='' && [...document.querySelectorAll('.cad-origem')].some(e=>e.innerText==='opção escolhida')`));
await shot("2_rascunho");

console.log("\n== exceção e segundo analista");
await preenche("#f-ncm", "7318.16.00");
await ok("NCM fora da regra vira exceção", await espera(`document.querySelector('[data-excecao="NCM_DIFERENTE_DA_REGRA|"]')||[...document.querySelectorAll('#checks')].some(e=>e.innerText.includes('NCM diferente'))`), (await texto("#checks")).replace(/\n/g, " ").slice(0, 150));
await ok("botão muda para revisão", (await texto("#c-aprovar")) === "Enviar para revisão", await texto("#c-aprovar"));
// editar e aprovar quase juntos: a aprovação espera a edição e não vira conflito falso
await preenche('[data-atr="COMPRIMENTO"]', "55MM");
await clica("#c-aprovar");
await ok("sem justificativa, o servidor recusa", await espera(`document.querySelector('#toast').classList.contains('erro')&&document.querySelector('#toast-t').innerText.includes('justificativa')`), await texto("#toast-t"));
await ok("edição seguida de aprovação não acusa conflito", !(await texto("#toast-t")).includes("Outra pessoa"), await texto("#toast-t"));
await ok("a edição foi aplicada", await espera(`document.querySelector('[data-atr="COMPRIMENTO"]').value==='55MM'`));
await ok("continua em rascunho", (await estado()) === "RASCUNHO");
const just = await ev(`[...document.querySelectorAll('[data-excecao]')].length`);
for (let i = 0; i < just; i++) await ev(`(()=>{const e=document.querySelectorAll('[data-excecao]')[${i}];e.focus();e.value='NCM confirmado pelo fiscal para este item';e.dispatchEvent(new Event('input',{bubbles:true}))})()`);
await ev(`(()=>{const b=document.querySelector('#c-aprovar');b.click();b.click()})()`);   // duplo clique
await ok("com justificativa, vai para revisão", await esperaEstado("EM_REVISAO"));
await pausa(400);
await ok("duplo clique não gera erro", !(await ev(`document.querySelector('#toast').classList.contains('erro')`)), await texto("#toast-t"));
await ok("cadastro em revisão não é duplicata de si mesmo", !(await texto("#checks")).includes("cadastro novo aprovado") && !(await texto("#similar")).includes("outro cadastro"), (await texto("#checks")).replace(/\n/g, " ").slice(0, 120));
await ok("legenda mostra a versão salva", (await texto("#cad-sub")).includes("salvas automaticamente"), await texto("#cad-sub"));
const urlCad = await ev("location.href");
await ok("o analista não decide a própria exceção", !(await existe("#c-rev-aprovar")));
await shot("3_em_revisao");
await usuario("bia|revisor");
await menu("revisao");
await ok("fila de revisão lista o cadastro", await espera(`document.querySelector('#rev-tabela tr[data-cadastro]')`), (await texto("#rev-tabela")).replace(/\n/g, " ").slice(0, 140));
await shot("4_revisao");
await clicaTexto("#rev-tabela button", "Decidir");
await ok("revisora vê a justificativa e decide", await espera(`document.querySelector('#c-rev-aprovar')`));
await clica("#c-rev-aprovar");
await ok("aprovado pela segunda pessoa", await esperaEstado("APROVADO"));
await clicaTexto("#cad-raiz button", "Sincronizar com o ERP");
await espera(`document.querySelector('#toast-t').innerText.includes('Sincroniz')`);
await menu("revisao");
await ok("envio ao ERP registrado", await espera(`document.querySelector('#rev-erp tbody tr')`), (await texto("#rev-erp")).replace(/\n/g, " ").slice(0, 120));
await shot("5_erp");

console.log("\n== recarregar a página");
await cdp("Page.navigate", { url: urlCad });
await ok("o endereço reabre o mesmo cadastro", await esperaEstado("APROVADO"));
await usuario("ana|analista");
await ok("cadastro decidido não é editável", await espera(`document.querySelector('[data-atr="BITOLA"]')&&document.querySelector('[data-atr="BITOLA"]').disabled`));

console.log("\n== pedidos");
await menu("pedidos");
await ok("indicadores e fila reais", await espera(`document.querySelector('#ped-tabela tr[data-pedido]')`), (await texto("#ped-kpis")).replace(/\n/g, " "));
await preenche("#ped-urg", "EMERGENCIAL");
await pausa(700);
await ok("filtro de urgência", await ev(`[...document.querySelectorAll('#ped-tabela tbody tr')].every(t=>t.innerText.includes('EMERGENCIAL'))`), await texto("#ped-total"));
await shot("6_pedidos");
const pedido = await ev(`document.querySelector('#ped-tabela tr[data-pedido]').dataset.pedido`);
await ev(`[...document.querySelectorAll('#ped-tabela tbody tr')].find(t=>t.dataset.pedido===${JSON.stringify(pedido)}).querySelector('button').click()`);
await ok("assumir abre o rascunho do pedido", await espera(`document.querySelector('#cad-titulo').innerText.includes(${JSON.stringify(pedido)})`), await texto("#cad-titulo"));
await ok("origem mostra o texto original", (await texto("#cad-raiz .cad-texto")).length > 5, (await texto("#cad-raiz .cad-texto")).slice(0, 90));
if (await existe("#c-confirmar")) {
  await clica("#c-confirmar");
  await ok("classe proposta precisa de confirmação humana", await espera(`!document.querySelector('#c-confirmar')`));
}
await shot("7_pedido");
await clica("#c-devolver");
await dialogoPreenche("Qual a folga necessária?");
await dialogoConfirma();
await ok("devolver ao solicitante", await esperaEstado("AGUARDANDO_SOLICITANTE"));
await ok("a pergunta aparece", (await texto("#cad-raiz")).includes("Qual a folga necessária?"));
await preenche("#c-resposta", "Folga C3");
await clica("#c-responder");
await ok("resposta devolve o rascunho", await esperaEstado("RASCUNHO"));

console.log("\n== usar código existente");
await clicaTexto("#cad-acoes button", "Voltar à lista");
await menu("cadastro");
await ok("lista os rascunhos em andamento", await espera(`document.querySelector('#cad-raiz tr[data-cadastro]')`));
await preenche("#cad-raiz .cad-ac .inp", "rolamento rigido");
await espera(`document.querySelector('.cad-ac-item')`);
await clica(".cad-ac-item");
await ok("escolher a classe cria o rascunho", await esperaEstado("RASCUNHO"));
await preenche('[data-atr="REFERENCIA"]', "SKF 6205-2RSH/C3");
await ok("a tabela técnica completa as medidas", await espera(`document.querySelector('[data-atr="DIAMETRO EXTERNO"]').value==='52MM'`), await valor('[data-atr="DIAMETRO EXTERNO"]'));
await ok("candidatos para a referência", await espera(`document.querySelector('#similar [data-usar]')`));
await shot("8_rolamento");
const alvo = await ev(`(()=>{const c=[...document.querySelectorAll('#similar .cand')].find(x=>x.dataset.nivel==='DIVERGENTE'&&x.querySelector('[data-usar]'));return c?c.dataset.code:null})()`);
if (alvo) {
  await clica(`#similar .cand[data-code="${alvo}"] [data-usar]`);
  await dialogoPreenche("curto");
  await dialogoConfirma();
  await ok("divergente exige justificativa de verdade", await espera(`document.querySelector('.cad-dlg-erro').innerText.includes('10')`), await texto(".cad-dlg-erro"));
  await dialogoPreenche("aplicação aceita, confirmado com o PCM");
  await dialogoConfirma();
  await ok("usar o código encerra como já existe", await esperaEstado("JA_EXISTE"), (await texto("#cad-raiz .callout")).replace(/\n/g, " "));
} else {
  await clica("#similar [data-usar]");
  await ok("usar o código encerra como já existe", await esperaEstado("JA_EXISTE"));
}

console.log("\n== reativação pela busca");
await menu("busca");
await clica("#b-limpar");
await preenche("#q", "rolamento rigido esferas 6206 borracha c3");
await espera(`document.querySelector('#cands .cand')`);
await preenche('[data-refino="FOLGA"]', "NORMAL");
await ok("refinar um atributo refaz a busca", await espera(`!document.querySelector('#b-leitura').innerText.includes('FOLGA:')`));
await preenche('[data-refino="FOLGA"]', "C3");
await espera(`document.querySelector('[data-refino="FOLGA"]').value==='C3'&&document.querySelector('#cands .cand')`);
await pausa(500);
const bloq = await ev(`(()=>{const c=[...document.querySelectorAll('#cands .cand')].find(x=>/BLOQUEADO|OBSOLETO/.test(x.innerText));return c?c.dataset.code:null})()`);
if (bloq) {
  await clica(`#cands .cand[data-code="${bloq}"]`);
  await ok("código inativo só por reativação", (await texto("#b-usar")).includes("reativação"), await texto("#b-usar"));
  await preenche("#b-just", "item descontinuado volta para a parada de 2027");
  await clica("#b-usar");
  await ok("reativação vai para o segundo analista", await esperaEstado("EM_REVISAO"));
} else console.log("(nenhum candidato inativo nesta busca: passo pulado)");

console.log("\n== fora do PDM");
await menu("busca");
await clica("#b-limpar");
await preenche("#q", "cadeira giratoria de escritorio");
await ok("avisa que nada no PDM parece com isso", await espera(`document.querySelector('#b-leitura').innerText.includes('Nada no PDM')`));
await clica("#b-novo");
await ok("rascunho sem classe abre", await esperaEstado("RASCUNHO"));
await ok("sem classe, oferece propor classe", await existe("#c-propor"));
await clica("#c-propor");
await dialogoPreenche("CADEIRA", "itens de escritório recorrentes nos pedidos");
await dialogoConfirma();
await ok("proposta aguarda o PDM", await esperaEstado("AGUARDANDO_CLASSE"));
await clicaTexto("#cad-raiz button", "Recusar");
await dialogoPreenche("mobiliário não é material MRO");
await dialogoConfirma();
await ok("recusar encerra fora do PDM", await esperaEstado("FORA_DO_PDM"));

console.log("\n== permissões e tema");
await usuario("leo|leitor");
await menu("cadastro");
await clicaTexto("#cad-acoes button", "Voltar à lista");
await espera(`document.querySelector('#cad-raiz tr[data-cadastro]')`);
await clicaTexto("#cad-raiz tr[data-cadastro] button", "Abrir");
await espera(`document.querySelector('#cad-estado')`);
await ok("leitor não edita nem aprova", !(await existe("#c-aprovar")));
await usuario("ana|analista");
await menu("cadastros");
await ok("acompanhamento lista os cadastros", await espera(`document.querySelector('#cads-tabela tr[data-cadastro]')`), await texto("#cads-total"));
await ev(`document.querySelector('.theme-btn').click()`);
await menu("cadastros");
await pausa(300);
await shot("9_cadastros_outro_tema");

console.log(`\n${passos - falhas} de ${passos} passaram`);
console.log("erros de JavaScript:", erros.length ? erros.slice(0, 4) : "nenhum");
console.log("respostas 5xx:", http.length ? http.slice(0, 4) : "nenhuma");
ws.close();
process.exit(falhas || erros.length || http.length ? 1 : 0);
