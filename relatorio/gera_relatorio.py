# -*- coding: utf-8 -*-
"""Gera o relatorio PDF 'Analise de mercado — Cadastro e saneamento de materiais' (VX/D01).

Todo numero externo tem citacao [n] na secao de referencias; cada fonte foi
re-verificada por fetch em 07/11/2026. Numeros internos vem do benchmark auditado
e da base do desafio (Serra Azul).
"""
import io
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (HRFlowable, Image, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

RAIZ = Path(__file__).resolve().parent
SAIDA = RAIZ / "Analise_de_Mercado_VX_D01.pdf"

# paleta (dataviz reference, modo claro)
AZUL = "#2a78d6"
TINTA = "#0b0b0b"
TINTA2 = "#52514e"
SUPERFICIE = "#fcfcfb"
VERDE = "#148556"
VERMELHO = "#c23c3c"
CINZA_LINHA = colors.HexColor("#d9d8d4")
AZUL_RL = colors.HexColor(AZUL)
TINTA_RL = colors.HexColor(TINTA)
TINTA2_RL = colors.HexColor(TINTA2)
ZEBRA = colors.HexColor("#f4f3f1")

ss = getSampleStyleSheet()
EST = {
    "titulo": ParagraphStyle("titulo", parent=ss["Title"], fontName="Helvetica-Bold",
                             fontSize=26, leading=31, textColor=TINTA_RL, alignment=TA_CENTER),
    "sub": ParagraphStyle("sub", parent=ss["Normal"], fontSize=13, leading=17,
                          textColor=TINTA2_RL, alignment=TA_CENTER),
    "h1": ParagraphStyle("h1", parent=ss["Heading1"], fontName="Helvetica-Bold",
                         fontSize=16, leading=20, textColor=TINTA_RL, spaceBefore=16, spaceAfter=6),
    "h2": ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold",
                         fontSize=12.5, leading=16, textColor=colors.HexColor("#1f4f8f"),
                         spaceBefore=10, spaceAfter=4),
    "corpo": ParagraphStyle("corpo", parent=ss["Normal"], fontSize=10, leading=14.5,
                            textColor=TINTA_RL, alignment=TA_JUSTIFY, spaceAfter=6),
    "nota": ParagraphStyle("nota", parent=ss["Normal"], fontSize=8.5, leading=11.5,
                           textColor=TINTA2_RL, spaceAfter=4),
    "ref": ParagraphStyle("ref", parent=ss["Normal"], fontSize=8.2, leading=11,
                          textColor=TINTA_RL, spaceAfter=3),
    "celula": ParagraphStyle("celula", parent=ss["Normal"], fontSize=8.6, leading=11,
                             textColor=TINTA_RL),
    "celula_b": ParagraphStyle("celula_b", parent=ss["Normal"], fontName="Helvetica-Bold",
                               fontSize=8.6, leading=11, textColor=TINTA_RL),
}


def P(txt, estilo="corpo"):
    return Paragraph(txt, EST[estilo])


def tabela(dados, larguras, cabecalho=True, fonte=8.6):
    t = Table(dados, colWidths=larguras, repeatRows=1 if cabecalho else 0)
    estilo = [
        ("FONTSIZE", (0, 0), (-1, -1), fonte),
        ("TEXTCOLOR", (0, 0), (-1, -1), TINTA_RL),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, TINTA_RL),
        ("LINEBELOW", (0, -1), (-1, -1), 0.4, CINZA_LINHA),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZEBRA]),
    ]
    if cabecalho:
        estilo += [("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]
    t.setStyle(TableStyle(estilo))
    return t


def grafico_economia():
    """Barras horizontais: economia anual recorrente por alavanca (cenario base)."""
    alav = [
        ("Custo de carregamento das duplicatas\n(12% da base [13] × 25% a.a. [17,18])", 6.0, False),
        ("Carregamento do excedente/obsoleto\n(8% da base [14] × 25% a.a.)", 4.0, False),
        ("Compra emergencial evitada\n(prêmio de 2–3× [16])", 1.0, True),
        ("Produtividade de catalogação\n(−60% tempo de revisão [8])", 0.4, True),
        ("Conformidade fiscal (NCM)\n(multa de 1% [22])", 0.1, True),
    ]
    rotulos = [a[0] for a in alav][::-1]
    vals = [a[1] for a in alav][::-1]
    est = [a[2] for a in alav][::-1]
    fig, ax = plt.subplots(figsize=(7.4, 3.4), dpi=200)
    fig.patch.set_facecolor(SUPERFICIE)
    ax.set_facecolor(SUPERFICIE)
    barras = ax.barh(range(len(vals)), vals, height=0.58, color=AZUL, zorder=3)
    for i, (b, v, e) in enumerate(zip(barras, vals, est)):
        if e:
            b.set_alpha(0.55)
        ax.text(v + 0.12, i, f"R$ {str(v).replace('.', ',')} mi" + (" *" if e else ""),
                va="center", ha="left", fontsize=8.5, color=TINTA)
    ax.set_yticks(range(len(rotulos)))
    ax.set_yticklabels(rotulos, fontsize=7.6, color=TINTA)
    ax.set_xlim(0, 7.4)
    ax.xaxis.set_visible(False)
    for lado in ("top", "right", "bottom"):
        ax.spines[lado].set_visible(False)
    ax.spines["left"].set_color("#d9d8d4")
    ax.tick_params(left=False)
    ax.set_title("Economia anual recorrente por alavanca — cenário base\n"
                 "(empresa com estoque MRO de R$ 200 mi; total R$ 11,5 mi/ano)",
                 fontsize=9.5, color=TINTA, loc="left", pad=10)
    fig.text(0.01, 0.01, "* estimativa própria conservadora; demais premissas com fonte citada",
             fontsize=7, color=TINTA2)
    buf = io.BytesIO()
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(buf, format="png", facecolor=SUPERFICIE, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


REFS = [
    # (n, titulo, url, tipo)
    (1, "Mordor Intelligence — Master Data Management Market Size & Forecasts (2026–2031)", "https://www.mordorintelligence.com/industry-reports/master-data-management-market", "pesquisa de mercado"),
    (2, "Mordor Intelligence — Data Quality Tools Market (2026–2031)", "https://www.mordorintelligence.com/industry-reports/data-quality-tools-market", "pesquisa de mercado"),
    (3, "W.W. Grainger — Form 10-K FY2025 (SEC EDGAR)", "https://www.sec.gov/Archives/edgar/data/277135/000027713526000011/gww-20251231.htm", "documento oficial"),
    (4, "Applied Industrial Technologies — Form 10-K FY2025 (SEC EDGAR)", "https://www.sec.gov/Archives/edgar/data/109563/000010956325000080/ait-20250630.htm", "documento oficial"),
    (5, "IBRAM — Setor Mineral 2025 (apresentação oficial, fev/2026)", "https://ibram.org.br/wp-content/uploads/2026/02/02.02.2026-Setor-Mineral-2025.pdf", "entidade setorial"),
    (6, "ABRADEE — Associação Brasileira de Distribuidores de Energia Elétrica", "https://abradee.org.br/", "entidade setorial"),
    (7, "Instituto Trata Brasil — Principais estatísticas (SINISA)", "https://tratabrasil.org.br/", "entidade setorial"),
    (8, "Verusen — Duplicate Material Identification", "https://verusen.com/duplicate-material-identification/", "fornecedor"),
    (9, "Verusen — MRO Inventory Optimization (casos de clientes)", "https://verusen.com/mro-inventory-optimization/", "fornecedor"),
    (10, "Verusen — The Death of the Data Cleanse", "https://verusen.com/the-death-of-the-data-cleanse/", "fornecedor"),
    (11, "IBM Think — What is Data Quality? (cita pesquisa Gartner)", "https://www.ibm.com/think/topics/data-quality", "fornecedor cita Gartner"),
    (12, "MIT Sloan Management Review — Seizing Opportunity in Data Quality (T. Redman, 2017)", "https://sloanreview.mit.edu/article/seizing-opportunity-in-data-quality/", "acadêmico/independente"),
    (13, "SpareTech Blog — Find & Remove Duplicates in Your Material Master", "https://sparetech.io/en/blog/find-and-remove-duplicates-material-master", "fornecedor"),
    (14, "SpareTech — página principal (benchmarks e casos Bosch/Brose)", "https://sparetech.io/en", "fornecedor"),
    (15, "Harvard Business Review — Bad Data Costs the U.S. $3 Trillion Per Year (2016)", "https://hbr.org/2016/09/bad-data-costs-the-u-s-3-trillion-per-year", "acadêmico/independente"),
    (16, "Verdantis — MRO Spend Management, Analysis & Cost Reduction", "https://www.verdantis.com/mro-spend-analysis/", "fornecedor"),
    (17, "Wikipedia — Carrying cost", "https://en.wikipedia.org/wiki/Carrying_cost", "referência geral"),
    (18, "Verdantis — MRO Category Management (caso −30% despesas MRO)", "https://www.verdantis.com/mro-category-management/", "fornecedor"),
    (19, "PiLog — Case study: Inventory Management in Mining Industry", "https://www.piloggroup.com/case-study/inventory-management-in-mining-industry/", "fornecedor"),
    (20, "PiLog Group — resultados por setor e caso mineradora global", "https://www.piloggroup.com/", "fornecedor"),
    (21, "Creactives — Case study CEMEX: Material & Service Master Data", "https://www.creactives.com/en/case-studies/cemex/", "fornecedor"),
    (22, "Medida Provisória 2.158-35/2001, art. 84 — Planalto", "https://www.planalto.gov.br/ccivil_03/mpv/2158-35.htm", "legislação"),
    (23, "Vendr Marketplace — Informatica (benchmark de contratos)", "https://www.vendr.com/marketplace/informatica", "benchmark de preços"),
    (24, "Vendr Marketplace — Stibo Systems (benchmark de contratos)", "https://www.vendr.com/marketplace/stibo-systems", "benchmark de preços"),
    (25, "PeerSpot — Informatica MDM Pricing (relatos de usuários)", "https://www.peerspot.com/products/informatica-mdm-pricing", "avaliações de usuários"),
    (26, "PeerSpot — SAP Master Data Governance Pricing (relatos de usuários)", "https://www.peerspot.com/products/sap-master-data-governance-pricing", "avaliações de usuários"),
    (27, "PeerSpot — Semarchy xDM Pricing (relatos de usuários)", "https://www.peerspot.com/products/semarchy-xdm-pricing", "avaliações de usuários"),
    (28, "Profisee — página oficial de Pricing", "https://profisee.com/pricing/", "fornecedor"),
    (29, "Verusen — site oficial (modelo comercial e garantia de ROI)", "https://www.verusen.com/", "fornecedor"),
    (30, "PiLog — Case study: Inventory Management in Petrochemical Industry", "https://www.piloggroup.com/case-study/inventory-manangement-in-petrochemical-industry", "fornecedor"),
    (31, "Dataversity — Why Data Quality Is the Biggest Key to MDM Success (2026)", "https://www.dataversity.net/articles/why-data-quality-is-the-biggest-key-to-mdm-success/", "imprensa especializada"),
    (32, "Hackathon VX — Briefing do Desafio VX/D01: Cadastro e saneamento de materiais", "arquivo do desafio (PDF)", "briefing oficial"),
]


def rodape(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(TINTA2_RL)
    canvas.drawString(18 * mm, 12 * mm, "Análise de mercado — Cadastro e saneamento de materiais · Hackathon VX/D01 · equipe vxwinners")
    canvas.drawRightString(A4[0] - 18 * mm, 12 * mm, f"página {doc.page}")
    canvas.restoreState()


doc = SimpleDocTemplate(str(SAIDA), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                        topMargin=16 * mm, bottomMargin=20 * mm,
                        title="Análise de mercado — Cadastro e saneamento de materiais (VX/D01)",
                        author="equipe vxwinners")
el = []

# ================================ CAPA ================================
el.append(Spacer(1, 48 * mm))
el.append(P("Cadastro e saneamento<br/>de materiais com IA", "titulo"))
el.append(Spacer(1, 6 * mm))
el.append(P("Análise de mercado e do problema — Hackathon VX · Desafio 01", "sub"))
el.append(Spacer(1, 3 * mm))
el.append(P("Equipe vxwinners · 07 de novembro de 2026", "sub"))
el.append(Spacer(1, 30 * mm))
el.append(HRFlowable(width="60%", thickness=1, color=AZUL_RL, hAlign="CENTER"))
el.append(Spacer(1, 4 * mm))
el.append(P("Baseado em MVP funcional com benchmark auditado (10 soluções × 4 campos, 23.554 itens)<br/>"
            "e em 31 fontes externas verificadas individualmente por re-consulta em 07/11/2026.", "sub"))
el.append(PageBreak())

# ========================== SUMÁRIO EXECUTIVO ==========================
el.append(P("Sumário executivo", "h1"))
el.append(P(
    "Toda operação industrial intensiva em ativos depende de um cadastro de materiais — e ele apodrece: "
    "o mesmo item ganha vários códigos, descrições fogem do padrão, NCM e unidade saem errados e campos "
    "críticos ficam vazios. O briefing do desafio [32] resume as quatro contas que a bagunça gera: capital "
    "parado, compra fragmentada, operação parada e risco fiscal. Benchmarks independentes dão a escala: "
    "má qualidade de dados custa em média US$ 12,9 milhões por ano por organização (Gartner [11]) e "
    "15%–25% da receita na estimativa de Thomas Redman (MIT SMR [12])."))
el.append(P(
    "Construímos um MVP que resolve o problema de ponta a ponta: classifica, deduplica, corrige NCM e "
    "preenche fabricante/part number combinando regras determinísticas, aprendizado de máquina clássico e "
    "LLM apenas onde ela paga o próprio custo — tudo medido num benchmark auditado com 10 soluções. Na base "
    "do desafio (R$ 200,9 mi de estoque), a solução destravou a identidade de R$ 101,2 mi em itens antes "
    "não-deduplicáveis e preencheu 35,3 mil campos por US$ 21 de computação."))
el.append(P(
    "Este relatório dimensiona o mercado (MDM global: US$ 21,6 bi em 2026 → US$ 50,9 bi em 2031 [1]), "
    "documenta casos reais de empresas nomeadas (CEMEX, Bruce Power, Bosch), modela a economia anual de "
    "R$ 5,7 mi a R$ 27 mi para uma empresa com estoque MRO de R$ 200 mi, e propõe precificação SaaS de "
    "R$ 180 mil a R$ 900 mil/ano — ancorada nos contratos reais de Informatica e Stibo [23,24] e em ROI "
    "mínimo de 10× para o cliente."))

# ============================ 1. O PROBLEMA ============================
el.append(P("1. O problema: a base que todo mundo usa e ninguém confia", "h1"))
el.append(P(
    "O cadastro de materiais é a fonte da verdade de compras, estoque, manutenção, recebimento e nota "
    "fiscal [32]. Ele se deteriora porque cada área cadastra do seu jeito, em texto livre, por décadas. "
    "Os quatro custos, nos termos do briefing [32]:"))
el.append(tabela(
    [[P("<b>Dor</b>", "celula_b"), P("<b>Mecanismo</b>", "celula_b"), P("<b>Evidência externa</b>", "celula_b")],
     [P("Capital parado", "celula"), P("O mesmo item estocado sob vários códigos", "celula"),
      P("9% das bases são duplicatas em média; 25% no caso Bosch [13,14]; 50–60% do estoque MRO típico é excedente/obsoleto/giro lento [10]", "celula")],
     [P("Compra fragmentada", "celula"), P("Itens iguais comprados separados, sem escala", "celula"),
      P("Catalogação otimizada reduziu 30% das despesas anuais de MRO em caso publicado [18]", "celula")],
     [P("Operação parada", "celula"), P("Manutenção espera peça que já estava no almoxarifado", "celula"),
      P("Compra emergencial custa 2–3× a planejada; até 90% das peças ficam paradas >1 ano [16]", "celula")],
     [P("Risco fiscal", "celula"), P("NCM errado em milhares de itens", "celula"),
      P("Multa de 1% do valor aduaneiro por classificação incorreta (MP 2.158-35/2001, art. 84) [22]", "celula")]],
    [28 * mm, 55 * mm, 91 * mm]))
el.append(Spacer(1, 3 * mm))
el.append(P(
    "Medimos as quatro dores na base do desafio (23.554 itens da mineradora fictícia Serra Azul): 79% das "
    "descrições fora do padrão PDM; 19 unidades de medida onde o padrão admite 5; fabricante vazio em 66,5% "
    "e part number em 78,5% dos itens; R$ 31,4 mi imobilizados em itens bloqueados/obsoletos com saldo; "
    "R$ 9,5 mi de base fiscal exposta por NCM ausente ou divergente; e R$ 103,0 mi (metade do valor do "
    "estoque) em itens cuja identidade — fabricante + part number — estava incompleta, tornando a "
    "deduplicação impossível."))
el.append(P(
    "Há ainda um gancho estratégico: a Gartner projeta que 60% dos projetos de IA serão abandonados até o "
    "fim de 2026 por falta de dados prontos para IA [31]. Saneamento de cadastro deixou de ser higiene "
    "operacional: é pré-requisito para qualquer agenda de IA industrial.", "corpo"))

# ============================ 2. MERCADO ============================
el.append(P("2. Mercado endereçável", "h1"))
el.append(P("2.1 O mercado de software (TAM)", "h2"))
el.append(P(
    "O mercado global de Master Data Management foi estimado em US$ 18,2 bi em 2025 e US$ 21,6 bi em 2026, "
    "com projeção de US$ 50,9 bi em 2031 (CAGR 18,7%) [1]. O mercado vizinho de ferramentas de qualidade de "
    "dados soma US$ 2,8 bi (2025) → US$ 7,4 bi (2031) [2]. Grandes empresas respondem por 63,3% da receita "
    "de MDM e a nuvem por 60,4% das implantações (2025) [1] — exatamente o perfil do nosso produto (SaaS "
    "para grandes operações)."))
el.append(P("2.2 O universo MRO que o produto arruma (contexto)", "h2"))
el.append(P(
    "O setor de MRO é 'grande e fragmentado': só a Grainger, maior distribuidora da América do Norte, vendeu "
    "US$ 17,9 bi em 2025 com mais de 1,5 milhão de produtos estocados [3]; a Applied Industrial estima "
    "mercado endereçável de ~US$ 80 bi só na América do Norte [4]. O gasto com MRO representa 0,5%–4,5% da "
    "receita em manufatura, e manutenção consome 5%–20% do orçamento de uma planta [16]. A Verusen, análogo "
    "direto do produto, declara já ter analisado US$ 138 bi em gastos MRO de clientes [8]."))
el.append(P("2.3 O alvo imediato no Brasil (SAM/SOM)", "h2"))
el.append(P(
    "Os segmentos do briefing [32] são grandes e concentrados no Brasil: a mineração faturou R$ 298,8 bi em "
    "2025, com US$ 76,9 bi de investimentos previstos para 2026–2030 e atividade em 2.760 municípios [5]; a "
    "distribuição de energia tem 42 concessionárias atendendo 90 milhões de unidades consumidoras [6]; o "
    "saneamento investiu R$ 29,1 bi só em 2024 [7]. Somando petróleo & gás, papel & celulose e siderurgia, "
    "estimamos um universo de 150–300 operações no Brasil com estoque MRO relevante (R$ 50 mi a R$ 1 bi+ "
    "cada). Capturando 40 contas em 3 anos com ticket médio de R$ 400 mil/ano (seção 6), o SOM é de "
    "~R$ 16 mi de receita recorrente anual — menos de 0,1% do TAM, premissa deliberadamente conservadora."))

# ============================ 3. CASOS REAIS ============================
el.append(P("3. Casos reais: quem já paga essa conta", "h1"))
el.append(P(
    "Casos publicados pelos próprios fornecedores de soluções (interpretá-los como resultados divulgados "
    "comercialmente, não auditoria independente — ainda assim, nomeiam empresas e cifras):"))
el.append(tabela(
    [[P("<b>Empresa / setor</b>", "celula_b"), P("<b>O que aconteceu</b>", "celula_b"), P("<b>Resultado divulgado</b>", "celula_b")],
     [P("Bruce Power (nuclear, Canadá)", "celula"),
      P("Otimização de dados e estoque MRO com IA (Verusen)", "celula"),
      P("US$ 42,2 mi identificados + US$ 18,1 mi adicionais [9]", "celula")],
     [P("CEMEX (cimento, 36 países)", "celula"),
      P("900 mil cadastros de materiais em 6 ERPs tratados com IA (Creactives)", "celula"),
      P("US$ 16 mi economizados; cadastro −20%; criação de itens novos −35% [21]", "celula")],
     [P("Bosch (autopeças)", "celula"),
      P("Diagnóstico de duplicidade no material master (SpareTech)", "celula"),
      P("25% do cadastro era duplicata; +50% de eficiência na checagem de spare parts [13,14]", "celula")],
     [P("Mineradora global (anônima)", "celula"),
      P("Saneamento de 5 mi de registros, 50 mil duplicatas (PiLog)", "celula"),
      P("US$ 30 mi (18 em manutenção + 12 em capital de giro); OEE +13 p.p. [20]", "celula")],
     [P("Mineradora de grande porte (anônima)", "celula"),
      P("400 mil registros MRO com 10 mil duplicatas (PiLog)", "celula"),
      P("US$ 35 mi+ de ganho; estoque −23% [19]", "celula")],
     [P("Petroquímica global (anônima)", "celula"),
      P("65 mil registros avaliados em US$ 155 mi; 11 mil duplicatas (PiLog)", "celula"),
      P("US$ 30,2 mi em capital desbloqueado [30]", "celula")],
     [P("Óleo & gás offshore (anônima)", "celula"),
      P("Visibilidade de estoque entre unidades da frota (Verusen)", "celula"),
      P("US$ 151 mi de oportunidade identificada; 10–20% de otimização de capital de giro [9]", "celula")],
     [P("Empresa global de nuvem (anônima)", "celula"),
      P("Dado ruim no cadastro de compras", "celula"),
      P("Pedido de compra de US$ 300 mil emitido para um único cabo [31]", "celula")]],
    [36 * mm, 68 * mm, 70 * mm]))
el.append(Spacer(1, 2 * mm))
el.append(P(
    "Outras empresas nomeadas com programas ativos de governança de cadastro de materiais: Enel, Siemens, "
    "AB InBev, Gestamp, BorgWarner (Creactives [21]), Domtar (Verusen [9]), Brose e ElringKlinger "
    "(SpareTech [14]). Em pesquisa aberta não localizamos casos brasileiros publicados com números — o que "
    "sinaliza espaço de posicionamento pioneiro no país, não ausência do problema.", "corpo"))

# ===================== 4. A SOLUÇÃO E A EVIDÊNCIA =====================
el.append(PageBreak())
el.append(P("4. A solução e a evidência (MVP medido)", "h1"))
el.append(P(
    "O MVP cobre as três frentes do briefing [32]: <b>saneamento</b> (deduplicação por chave de identidade "
    "após normalização), <b>cadastro</b> (API de sugestão em 19 ms integrada à interface: grupo, NCM, "
    "fabricante, referência e alerta de duplicata antes de criar o item) e <b>enriquecimento</b> "
    "(preenchimento dos campos vazios com confiança e origem por valor). A arquitetura usa LLM apenas onde "
    "há conhecimento de mundo a ganhar; o resto é determinístico e auditável. Benchmarkamos 10 soluções "
    "por avaliação mascarada (teste congelado de 1.500–2.000 itens/campo), com métricas recalculadas por "
    "verificador independente e auditoria de vazamento:"))
el.append(tabela(
    [[P("<b>Campo</b>", "celula_b"), P("<b>Melhor solução</b>", "celula_b"), P("<b>Top-1</b>", "celula_b"),
      P("<b>Top-3</b>", "celula_b"), P("<b>Custo/1k itens</b>", "celula_b"), P("<b>LLM ingênua (comparador)</b>", "celula_b")],
     [P("Grupo de mercadoria", "celula"), P("TF-IDF + regr. logística", "celula"), P("96,5%*", "celula"),
      P("97,2%", "celula"), P("US$ 0", "celula"), P("0% (não conhece códigos privados)", "celula")],
     [P("NCM", "celula"), P("TF-IDF + regr. logística", "celula"), P("91,1%", "celula"),
      P("99,0%", "celula"), P("US$ 0", "celula"), P("42,7% (Sonnet) / 76,6% (Fable 5)", "celula")],
     [P("Fabricante", "celula"), P("Cascata regras → LLM", "celula"), P("84,3%", "celula"),
      P("93,3%", "celula"), P("US$ 0,51", "celula"), P("78,1%", "celula")],
     [P("Part number", "celula"), P("Extração por regras", "celula"), P("84,4%", "celula"),
      P("93,3%", "celula"), P("US$ 0", "celula"), P("80,6%", "celula")]],
    [34 * mm, 38 * mm, 18 * mm, 18 * mm, 26 * mm, 40 * mm]))
el.append(P("* teto imposto por ~3,5% de ruído plantado no gabarito do desafio; na inspeção manual dos erros, "
            "o NCM da própria base apoiou o modelo em 27 casos e o gabarito em 0.", "nota"))
el.append(P(
    "Resultado aplicado à base Serra Azul: identidade (fabricante + part number) destravada em 5.055 dos "
    "5.290 itens que valiam R$ 103,0 mi — <b>R$ 101,2 mi agora deduplicáveis</b>; 1.173 NCMs preenchidos "
    "(99% de acerto em 3 candidatos); 35,3 mil campos processados por <b>US$ 21</b> de computação, contra "
    "~1.770 horas de trabalho manual equivalente. O modelo mais caro do mercado (Claude Fable 5, US$ 10/50 "
    "por MTok) foi testado e não liderou nenhum campo — evidência de que o gargalo é informação, não "
    "inteligência, e de que a arquitetura híbrida é a economicamente correta."))

# ===================== 5. ECONOMIA ANUAL =====================
el.append(P("5. Quanto uma empresa economiza por ano", "h1"))
el.append(P(
    "Modelo para uma empresa de referência com estoque MRO de R$ 200 mi (porte da Serra Azul; mineradoras e "
    "utilities médias/grandes). Cada premissa tem fonte; onde não há benchmark publicado, a linha está "
    "marcada como estimativa própria conservadora."))
el.append(Image(grafico_economia(), width=168 * mm, height=79 * mm))
el.append(Spacer(1, 2 * mm))
el.append(tabela(
    [[P("<b>Alavanca (premissas com fonte)</b>", "celula_b"), P("<b>Conservador</b>", "celula_b"),
      P("<b>Base</b>", "celula_b"), P("<b>Agressivo</b>", "celula_b")],
     [P("Duplicatas na base: 9% / 12% / 25% [13,14] × custo de carregamento 20% / 25% / 30% a.a. [17,18]", "celula"),
      P("R$ 3,6 mi", "celula"), P("R$ 6,0 mi", "celula"), P("R$ 15,0 mi", "celula")],
     [P("Excedente/obsoleto adicional identificado: 4% / 8% / 15% da base [14,10] × carregamento", "celula"),
      P("R$ 1,6 mi", "celula"), P("R$ 4,0 mi", "celula"), P("R$ 9,0 mi", "celula")],
     [P("Compra emergencial evitada (prêmio 2–3× [16]) + produtividade de catalogação (−60% tempo [8]) + fiscal [22] — estimativa própria", "celula"),
      P("R$ 0,5 mi", "celula"), P("R$ 1,5 mi", "celula"), P("R$ 3,0 mi", "celula")],
     [P("<b>Economia recorrente total / ano</b>", "celula_b"),
      P("<b>R$ 5,7 mi</b>", "celula_b"), P("<b>R$ 11,5 mi</b>", "celula_b"), P("<b>R$ 27,0 mi</b>", "celula_b")],
     [P("Liberação de capital (one-off): redução de estoque de 10% / 20% / 30% [9,14,19]", "celula"),
      P("R$ 20 mi", "celula"), P("R$ 40 mi", "celula"), P("R$ 60 mi", "celula")]],
    [96 * mm, 26 * mm, 26 * mm, 26 * mm]))
el.append(Spacer(1, 2 * mm))
el.append(P(
    "O modelo é coerente com os resultados divulgados pelo mercado: PiLog reporta 12–15% de redução de custo "
    "de estoque e casos de US$ 30–35 mi em mineração [19,20]; Verusen, 20% de redução líquida de capital de "
    "giro MRO e ROI de 10× no primeiro ano [8,9]; Verdantis, −30% de despesas anuais de MRO [18]. Projetos "
    "tradicionais de limpeza custam US$ 500 mil–2 mi+ em escala enterprise, demoram 3–12 meses e a base "
    "volta a sujar [10] — nosso produto substitui esse gasto recorrente por software contínuo com sugestão "
    "no momento do cadastro (a regra 1-10-100: prevenir custa 1, corrigir custa 10, ignorar custa 100 "
    "[13,31])."))

# ===================== 6. PRECIFICAÇÃO =====================
el.append(P("6. Precificação do produto", "h1"))
el.append(P("6.1 Âncoras de mercado", "h2"))
el.append(tabela(
    [[P("<b>Produto análogo</b>", "celula_b"), P("<b>Preço observado</b>", "celula_b"), P("<b>Modelo de cobrança</b>", "celula_b")],
     [P("Informatica (MDM)", "celula"), P("mediana US$ 56,3 mil/ano; faixa US$ 10,8–252,7 mil (36 contratos) [23]; relatos de US$ 160 mil a ~US$ 1 mi/ano [25]", "celula"),
      P("nº de registros master + usuários; nuvem por consumo (IPU); manutenção 20–22%/ano [23]", "celula")],
     [P("Stibo Systems (STEP)", "celula"), P("mediana US$ 97,4 mil/ano [24]", "celula"), P("assinatura enterprise", "celula")],
     [P("SAP MDG", "celula"), P("percebido como 'muito caro' [26]", "celula"), P("por usuário/transação; nuvem por assinatura [26]", "celula")],
     [P("Semarchy xDM", "celula"), P("posicionado abaixo de Informatica/Profisee [27]", "celula"), P("por golden record [27]", "celula")],
     [P("Profisee", "celula"), P("preço 'médio de mercado' (cotação) [28]", "celula"), P("volume de registros, agnóstico a domínio [28]", "celula")],
     [P("Verusen (análogo direto)", "celula"), P("assinatura anual; garantia de ROI mínimo de 3× [29]", "celula"), P("assinatura + gain-share implícito via garantia [29]", "celula")]],
    [30 * mm, 78 * mm, 66 * mm]))
el.append(P("6.2 Nossa proposta", "h2"))
el.append(tabela(
    [[P("<b>Plano</b>", "celula_b"), P("<b>Para quem</b>", "celula_b"), P("<b>Assinatura</b>", "celula_b"), P("<b>Inclui</b>", "celula_b")],
     [P("Essencial", "celula"), P("até 50 mil itens, 1 ERP", "celula"), P("R$ 180 mil/ano", "celula"),
      P("saneamento inicial + API de sugestão + painel de duplicatas", "celula")],
     [P("Profissional", "celula"), P("até 250 mil itens", "celula"), P("R$ 420 mil/ano", "celula"),
      P("+ enriquecimento contínuo com LLM, fila de revisão, NCM fiscal", "celula")],
     [P("Enterprise", "celula"), P("1 mi+ itens, multi-ERP", "celula"), P("R$ 900 mil+/ano", "celula"),
      P("+ integrações ERP, SLA, modelos dedicados, gain-share opcional", "celula")]],
    [24 * mm, 40 * mm, 30 * mm, 80 * mm]))
el.append(Spacer(1, 2 * mm))
el.append(P(
    "Racional: (i) <b>value-based</b> — o plano Profissional (R$ 420 mil ≈ US$ 75 mil/ano) captura menos de "
    "4% da economia recorrente do cenário base (R$ 11,5 mi/ano), entregando ROI > 25× — acima da garantia de "
    "3× da Verusen [29] e do ROI de 10× que ela divulga [9]; (ii) <b>ancoragem competitiva</b> — o ticket "
    "fica entre a mediana da Informatica (US$ 56 mil) e a da Stibo (US$ 97 mil) [23,24], abaixo dos relatos "
    "de ~US$ 1 mi/ano do MDM tradicional [25]; (iii) <b>cobrança por volume de itens</b>, o padrão do setor "
    "(Profisee, Semarchy) [27,28], transparente e alinhada ao valor; (iv) <b>implantação</b> (saneamento "
    "inicial assistido) cobrada à parte, a 0,8–1,2× a assinatura — substituindo projetos de limpeza de "
    "US$ 500 mil–2 mi [10] por entrega em semanas (nosso preenchimento completo custou US$ 21 de "
    "computação); (v) <b>gain-share opcional</b> no Enterprise: 10% da economia verificada no ano 1, com "
    "teto — espelha a assimetria de risco que o mercado já aceita [29]. Com 40 contas no mix (SOM, seção "
    "2.3): ~R$ 16 mi de ARR no ano 3."))

# ===================== 7. RISCOS E LIMITAÇÕES =====================
el.append(P("7. Riscos e limitações desta análise", "h1"))
el.append(P(
    "(1) Vários benchmarks de economia vêm de material comercial de fornecedores (Verusen, PiLog, SpareTech, "
    "Verdantis) — são 'resultados divulgados', não auditorias; usamos sempre a ponta conservadora e marcamos "
    "estimativas próprias. (2) O MVP foi medido num dataset sintético realista do desafio; os tetos de "
    "acurácia (96,5% em grupo, 86,6% em part number) refletem ruído plantado e ausência real de informação — "
    "em bases reais os tetos variam. (3) Não localizamos casos brasileiros publicados com cifras; o mercado "
    "local pode exigir evangelização. (4) Preços de concorrentes vêm de marketplaces de contratos e relatos "
    "de usuários [23–28], não de tabelas oficiais. (5) A economia one-off (liberação de capital) depende de "
    "execução da consolidação física de estoque, não só do software."))

# ===================== REFERÊNCIAS =====================
el.append(PageBreak())
el.append(P("Referências", "h1"))
el.append(P("Todas as URLs foram acessadas e verificadas individualmente em 07/11/2026 (re-consulta por "
            "verificador independente; apenas fontes confirmadas foram citadas).", "nota"))
for n, titulo, url, tipo in REFS:
    el.append(P(f"[{n}] {titulo} — <i>{tipo}</i>. {url}", "ref"))

doc.build(el, onFirstPage=rodape, onLaterPages=rodape)
print(f"gerado: {SAIDA} ({SAIDA.stat().st_size/1024:.0f} KB)")
