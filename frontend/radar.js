/* Radar, ligado aos dados que o projeto tem.
 *
 * Lê artefatos/radar.json (publicado em /frontend/dados/), gerado por
 * scripts/20_radar.py a partir do plano de junção, do saneado, da fila de
 * intervenção e dos gabaritos. Cada número carrega a própria procedência, e o
 * selo da tela vem do JSON — não do HTML — para o selo não poder discordar do
 * número que está ao lado.
 *
 *   medido      sai de um artefato do pipeline ou de um gabarito
 *   estimado    cálculo sobre a base, com a premissa dita
 *   premissa    parâmetro ajustável (o custo de capital, por exemplo)
 *   não medido  não existe medição: a tela diz isso em vez de mostrar número
 *
 * Antes desta ligação, o topo do Radar trazia "Capital já consolidado R$ 4,7 mi
 * — medido" sem nenhuma unificação executada, "312 reservas" e "87 NF-e" que
 * não saíam de lugar nenhum, e uma série de seis meses inventada no gráfico.
 */
(function () {
  "use strict";

  const ARQ = "frontend/dados/radar.json";
  const ALT = "http://127.0.0.1:8000/frontend/dados/radar.json";
  const SELO = { medido: "src-med", estimado: "src-est", premissa: "src-pre" };
  const NOME_SELO = { medido: "medido", estimado: "estimado", premissa: "premissa" };

  const $ = (s) => document.querySelector(s);
  const brlMi = (v) =>
    "R$ " + (v / 1e6).toFixed(2).replace(".", ",") + " mi";
  const inteiro = (v) => (v || 0).toLocaleString("pt-BR");

  function cartao(d) {
    // o tipo vem do JSON: adivinhar pela magnitude fazia 1.104 NCMs corrigidos
    // aparecerem como "R$ 0,00 mi"
    const valor = typeof d.valor !== "number" ? d.valor
      : d.tipo === "inteiro" ? inteiro(d.valor)
      : brlMi(d.valor);
    const cor = d.fonte === "medido" && d.valor === 0 ? "var(--text-2)"
      : d.rotulo && d.rotulo.indexOf("fila") >= 0 ? "var(--warn)" : "";
    return `<div class="card hero" data-tt="${d.rotulo}|${d.detalhe}|fonte: ${d.origem}">
      <div class="l">${d.rotulo} <span class="src-tag ${SELO[d.fonte] || "src-pre"}">${
      NOME_SELO[d.fonte] || d.fonte}</span></div>
      <div class="v"${cor ? ` style="color:${cor}"` : ""}>${valor}</div>
      <div class="s">${d.detalhe}</div>
    </div>`;
  }

  function pinta(radar) {
    window.RADAR = radar;

    const hero = $("#rad-hero");
    if (hero) {
      const h = radar.hero;
      hero.innerHTML = [h.consolidavel, h.consolidado, h.oportunidade, h.fila, h.ncm]
        .map(cartao).join("");
    }

    // Os dois KPIs da home (casca plataforma.html). Vêm do mesmo JSON do Radar
    // para a primeira tela não poder discordar da tela do dinheiro: era ali que
    // estava "R$ 4,7 mi · capital já consolidado (medido)" sem medição alguma.
    // O texto de apoio é recortado do próprio `detalhe`, nunca remontado aqui.
    const kpi = (idv, idd, d, trecho) => {
      const v = $("#" + idv), s = $("#" + idd);
      if (!v) return;
      v.textContent = brlMi(d.valor);
      if (d.fonte === "medido" && d.valor === 0) v.style.color = "var(--text-2)";
      if (s && d.detalhe) s.textContent = trecho(d.detalhe);
    };
    kpi("home-consolidavel", "home-consolidavel-d", radar.hero.consolidavel,
        (t) => t.split(" · ").slice(0, 2).join(" · "));
    kpi("home-consolidado", "home-consolidado-d", radar.hero.consolidado,
        (t) => t.split(":")[0]);

    // Contagem de grupos de duplicidade, nos pontos da casca que a traziam
    // escrita a mao (1.412, quando o plano tem 1.991). Este JSON ja está
    // baixado aqui, então não custa rede nenhuma a mais.
    const grupos = (radar.base || {}).grupos;
    if (typeof grupos === "number") {
      ["n-clusters", "n-clusters-home", "n-clusters-fila"].forEach((id) => {
        const n = $("#" + id);
        if (n) n.textContent = inteiro(grupos);
      });
    }

    // o que não tem medição aparece dito, não escondido
    const nm = $("#rad-naomedido");
    if (nm && (radar.nao_medido || []).length) {
      nm.innerHTML = radar.nao_medido.map((x) =>
        `<div style="display:flex;gap:10px;align-items:baseline;margin:6px 0">
           <span class="badge">não medido</span>
           <div><b style="font-size:12.5px">${x.rotulo}</b>
             <div class="faint" style="font-size:12px">${x.motivo}</div></div>
         </div>`).join("");
      $("#rad-naomedido-card").style.display = "";
    }

    // evidência de eficácia medida contra os gabaritos, ao lado das premissas
    const prem = $("#r-opp");
    if (prem && !$("#rad-eficacia-card")) {
      const card = document.createElement("div");
      card.className = "card";
      card.id = "rad-eficacia-card";
      card.style.marginBottom = "16px";
      card.innerHTML = `<div class="card-h"><h3>Eficácia medida contra o gabarito</h3>
          <span class="sub">conjunto-ouro anotado sem olhar a saída do pipeline</span>
          <div class="r"><span class="src-tag src-med">medido</span></div></div>
        <div style="overflow:auto"><table class="tbl"><thead><tr>
          <th>indicador</th><th>valor</th><th>detalhe</th><th>fonte</th>
        </tr></thead><tbody>${radar.eficacia.map((e) => `<tr>
          <td>${e.rotulo}</td><td class="mono">${e.valor}</td>
          <td class="wrap faint">${e.detalhe || ""}</td>
          <td class="mono faint" style="font-size:11px">${e.origem || ""}</td></tr>`).join("")}
        </tbody></table></div>`;
      const alvoPai = prem.closest(".card");
      if (alvoPai && alvoPai.parentNode) alvoPai.parentNode.insertBefore(card, alvoPai);
    }

    // premissas: a lista do JSON, abaixo dos controles existentes
    const lista = $("#rad-premissas");
    if (lista) {
      lista.innerHTML = radar.premissas.map((x) =>
        `<div style="display:flex;gap:8px;font-size:12px;margin:4px 0">
           <span style="color:var(--text-2)">${x.rotulo}</span>
           <span class="mono" style="margin-left:auto">${x.valor}</span>
         </div><div class="faint" style="font-size:11px;margin-bottom:8px">${x.nota}</div>`
      ).join("");
    }

    // as funções do próprio Radar, agora com dado real por baixo
    if (typeof trendChart === "function") trendChart();
    if (typeof healthTiles === "function") healthTiles();
    if (typeof radarCalc === "function") radarCalc();

    const g = $("#rad-gerado");
    if (g) g.textContent = "dados de " + (radar.gerado_em || "").replace("T", " ");
  }

  async function carrega() {
    if (!$("#rad-hero")) return;
    for (const url of [ARQ, ALT]) {
      try {
        const r = await fetch(url, { cache: "no-store" });
        if (!r.ok) continue;
        pinta(await r.json());
        return;
      } catch (e) { /* tenta a próxima */ }
    }
    $("#rad-hero").innerHTML =
      `<div class="card" style="grid-column:1/-1;padding:16px;line-height:1.7">
         <b>Não achei os dados do Radar.</b>
         <div class="pdm-preview" style="margin-top:8px">uv run --no-project --with pandas --with openpyxl python scripts/20_radar.py</div>
         <div class="faint" style="margin-top:8px">e abra a plataforma pelo servidor (./rodar.sh).</div>
       </div>`;
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", carrega);
  else carrega();
})();
