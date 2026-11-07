"""Orquestracao das quatro camadas.

  1 regras lexicas  -> 2 BERT  -> 3 arbitro  -> 4 LLM (so no residuo)  -> validador

O validador fecha o circuito: nenhum valor entra no registro saneado sem passar
pelas invariantes do PDM, independentemente da camada que o propos.
"""

from __future__ import annotations

import re

from dataclasses import dataclass, field

from .arbitro import ESTADOS_REVISAO, Arbitro, Decisao, Resultado
from .bert import ExtratorBert
from .llm import DesempateLlm
from .pdm import Pdm
from .regras import Candidato, ClassificadorLexico, ExtratorLexico
from .texto import expandir, juntar, normalizar, normalizar_estrutura
from .validador import Validador

# Rotulo de um par "ATRIBUTO: VALOR": o nome antes dos dois pontos. Mesma forma
# que rotulos.RX_PAR usa para gerar o treino, para treino e inferencia verem o
# mesmo texto.
RX_ROTULO = re.compile(r"(?:^|[;,])\s*[A-Z][A-Z0-9/ ]{0,28}?\s*:")

# Estados finais do registro
SANEADO = "SANEADO"            # todos os obrigatorios preenchidos e chave de identidade fechada
PENDENTE = "PENDENTE"          # falta obrigatorio que o texto nao informa -> enriquecimento
REVISAO = "REVISAO_HUMANA"     # conflito que nem o LLM resolveu
FORA_DO_PDM = "FORA_DO_PDM"    # nao existe classe para o item


@dataclass
class RegistroSaneado:
    codigo: str
    estado: str
    id_pdm: str = ""
    substantivo: str = ""
    qualificador: str = ""
    grupo: str = ""
    confianca_sujeito: float = 0.0
    empate_sujeito: tuple[str, ...] = ()
    grupo_corrigido: bool = False
    descricao_original: str = ""
    descricao_pdm: str = ""
    descricao_curta: str = ""
    unidade_original: str = ""
    unidade_pdm: str | None = None
    unidade_motivo: str = ""
    ncm_original: str = ""
    ncm_pdm: str | None = None
    ncm_motivo: str = ""
    chave_identidade: str | None = None
    completude: float = 0.0
    discordancia: float = 0.0
    escalado: bool = False
    motivos_escalada: list[str] = field(default_factory=list)
    pendentes: list[str] = field(default_factory=list)
    conflitos: list[str] = field(default_factory=list)
    decisoes: dict[str, Decisao] = field(default_factory=dict)

    def como_dict(self) -> dict:
        return {
            "CODIGO_MATERIAL": self.codigo,
            "ESTADO": self.estado,
            "ID_PDM": self.id_pdm,
            "GRUPO_CORRIGIDO": int(self.grupo_corrigido),
            "SUBSTANTIVO": self.substantivo,
            "QUALIFICADOR": self.qualificador,
            "DESCRICAO_ORIGINAL": self.descricao_original,
            "DESCRICAO_PDM": self.descricao_pdm,
            "DESCRICAO_CURTA_PDM": self.descricao_curta,
            "UNIDADE_ORIGINAL": self.unidade_original,
            "UNIDADE_PDM": self.unidade_pdm or "",
            "UNIDADE_MOTIVO": self.unidade_motivo,
            "NCM_ORIGINAL": self.ncm_original,
            "NCM_PDM": self.ncm_pdm or "",
            "NCM_MOTIVO": self.ncm_motivo,
            "CHAVE_IDENTIDADE": self.chave_identidade or "",
            "COMPLETUDE": round(self.completude, 3),
            "DISCORDANCIA": round(self.discordancia, 3),
            "ESCALADO_LLM": int(self.escalado),
            "MOTIVOS_ESCALADA": " | ".join(self.motivos_escalada),
            "PENDENTES": " | ".join(self.pendentes),
            "CONFLITOS": " | ".join(self.conflitos),
            "FONTES": " | ".join(
                f"{k}={v.fonte}" for k, v in self.decisoes.items() if v.valor
            ),
        }


class Pipeline:
    def __init__(self, pdm: Pdm, bert: ExtratorBert | None = None,
                 llm: DesempateLlm | None = None, arbitro: Arbitro | None = None,
                 aprendizado=None):
        self.pdm = pdm
        self.validador = Validador(pdm)
        self.clf = ClassificadorLexico(pdm)
        self.aprendizado = aprendizado
        self.regras = ExtratorLexico(pdm, aprendizado=aprendizado)
        self._palavras_de_rotulo: set[str] | None = None
        self.bert = bert
        self.llm = llm
        self.arbitro = arbitro or Arbitro(self.validador)
        self.contador = {"total": 0, SANEADO: 0, PENDENTE: 0, REVISAO: 0, FORA_DO_PDM: 0,
                         "escalados": 0, "falhas_llm": 0}
        self.ultimo_erro_llm = ""

    # ------------------------------------------------------------- bert

    def _bert(self, texto: str, classe) -> dict[str, Candidato]:
        if self.bert is None:
            return {}
        tokens = self._tokens_para_bert(texto)
        if not tokens:
            return {}
        validos = {a.nome for a in classe.atributos}
        saida: dict[str, Candidato] = {}
        for p in self.bert.prever(tokens):
            if p.atributo not in validos:
                continue                      # mascara pela classe prevista
            atual = saida.get(p.atributo)
            if atual is None or p.confianca > atual.confianca:
                saida[p.atributo] = Candidato(
                    atributo=p.atributo, valor=p.valor, fonte="bert",
                    confianca=p.confianca, evidencia=p.valor,
                )
        return saida

    def _tokens_para_bert(self, texto: str) -> list[str]:
        """Prepara o texto do mesmo jeito que o gerador de rotulos preparou o treino.

        Corrige um train/serve skew real: `rotulos.py` apaga o NOME do atributo
        do texto de treino (sem isso o modelo so aprenderia a copiar o que vem
        depois dos dois pontos e seria inutil nos registros telegraficos). Mas o
        texto de inferencia ainda contem esses nomes, e o modelo - que nunca os
        viu - passa a trata-los como VALOR: 3.141 registros tiveram a palavra
        'FABRICANTE' etiquetada como valor de MATERIAL.

        Remove exatamente o que o treino removeu: o rotulo de um par
        'ATRIBUTO: VALOR'. Texto telegrafico, que nao tem rotulo, passa intacto.
        Filtrar por lista de palavras seria cego - apagaria 'PARAFUSO' (que e o
        sujeito) e manteria 'ACABAMENTO' (que tambem e valor, em SEM ACABAMENTO).
        """
        estruturado = normalizar_estrutura(texto)
        if ":" in estruturado:
            # remove o rotulo, preserva o valor que vem depois
            limpo = RX_ROTULO.sub(" ", estruturado)
        else:
            limpo = estruturado
        return expandir(limpo).split()

    # ------------------------------------------------------------- registro

    def processar(self, registro: dict) -> RegistroSaneado:
        self.contador["total"] += 1
        codigo = str(registro.get("CODIGO_MATERIAL", ""))
        grupo = str(registro.get("GRUPO_MERCADORIA", "") or "").strip()
        # juntar() evita repetir conteudo: DESCRICAO_CURTA costuma ser truncamento
        # da LONGA, e o texto duplicado quebra a contagem de grandezas
        texto = juntar(*(
            str(registro.get(c, "") or "")
            for c in ("DESCRICAO_LONGA", "DESCRICAO_CURTA", "FABRICANTE", "REFERENCIA_FABRICANTE")
        ))
        original = str(registro.get("DESCRICAO_LONGA", "") or "")

        sujeito = self.clf.classificar(texto, grupo)
        if sujeito.classe is None:
            self.contador[FORA_DO_PDM] += 1
            return RegistroSaneado(
                codigo=codigo, estado=FORA_DO_PDM, grupo=grupo,
                descricao_original=original,
                motivos_escalada=["nenhuma classe do PDM casa com o substantivo"],
            )

        classe = sujeito.classe
        cand_regras = self.regras.extrair(texto, classe, sujeito.substantivo)
        cand_bert = self._bert(texto, classe)
        res: Resultado = self.arbitro.arbitrar(classe, cand_regras, cand_bert,
                                               sujeito.confianca, sujeito.substantivo)

        escalado = False
        if res.escalar and self.llm is not None:
            foco = [d.atributo for d in res.em_estado("CONFLITO", "AMBIGUO", "INCERTO", "INVALIDO")]
            resposta = self.llm.desempatar(classe, texto, foco, res.motivos_escalada)
            if resposta.valores:
                res = self.arbitro.incorporar_llm(
                    classe, res, resposta.valores,
                    evidencias=resposta.evidencias, aprendizado=self.aprendizado)
                escalado = True
                self.contador["escalados"] += 1
            elif resposta.erro:
                # Falha do LLM nao pode passar por "rodou e nao achou nada": com o
                # modelo errado configurado, 100% das chamadas falham e o relatorio
                # mostraria resultado normal. Conta e registra no motivo do registro.
                self.contador["falhas_llm"] += 1
                self.ultimo_erro_llm = resposta.erro
                res.motivos_escalada.append(f"LLM indisponivel: {resposta.erro[:120]}")

        return self._montar(registro, classe, sujeito, res, escalado, texto, original, codigo, grupo)

    # Colunas proprias do ERP que alimentam caixas de atributo homonimas.
    # Sao fonte legitima e, nas classes de referencia do fabricante, costumam ser
    # a UNICA fonte: REFERENCIA FABRICANTE e caixa de formato livre, que a regra
    # nao consegue recortar do texto.
    COLUNA_PARA_CAIXA = {
        "FABRICANTE": "FABRICANTE",
        "REFERENCIA_FABRICANTE": "REFERENCIA FABRICANTE",
    }

    def _preencher_das_colunas(self, registro, classe, res) -> None:
        """Completa caixa vazia com o valor da coluna do ERP, se houver.

        Sem isso a chave de identidade fecha pela coluna enquanto a descricao
        imprime <PENDENTE> para o mesmo atributo - duas verdades diferentes para
        o mesmo registro. O valor passa pelo validador como qualquer outro.
        """
        for coluna, nome in self.COLUNA_PARA_CAIXA.items():
            bruto = str(registro.get(coluna, "") or "").strip()
            d = res.decisoes.get(nome)
            if not bruto or d is None or d.valor:
                continue
            atributo = next((a for a in classe.atributos if a.nome == nome), None)
            if atributo is None:
                continue
            v = self.validador.valor(atributo, bruto)
            if not v.ok:
                d.motivo = f"{d.motivo}; coluna {coluna}={bruto!r} recusada: {v.motivo}"
                continue
            d.valor, d.fonte, d.estado = v.valor, "coluna_erp", "ACEITO"
            d.confianca = 0.95
            d.evidencia = f"coluna {coluna}"
            d.motivo = f"preenchido pela coluna {coluna} do cadastro"

    def _aprender_do_bert(self, classe, res) -> None:
        """Guarda o que o BERT recortou e o validador aprovou.

        So caixa TEXTUAL (vocabulario fechado): em caixa NUMERICA o par
        termo->valor nao generaliza, porque a atribuicao e posicional.
        """
        if self.aprendizado is None:
            return
        por_nome = {a.nome: a for a in classe.atributos}
        for d in res.decisoes.values():
            if d.fonte not in ("bert", "bert_desempata") or not d.valor or not d.evidencia:
                continue
            atributo = por_nome.get(d.atributo)
            if atributo is not None and atributo.fechado:
                self.aprendizado.aprender(atributo, d.evidencia, d.valor,
                                          "bert", classe.id_pdm)

    def _montar(self, registro, classe, sujeito, res, escalado, texto, original, codigo, grupo):
        self._aprender_do_bert(classe, res)
        self._preencher_das_colunas(registro, classe, res)
        obrigatorios = [a.nome for a in classe.obrigatorios if a.nome in res.decisoes]
        if obrigatorios:
            res.completude = sum(1 for n in obrigatorios if res.decisoes[n].valor) / len(obrigatorios)

        valores = res.valores
        fabricante = valores.get("FABRICANTE") or str(registro.get("FABRICANTE", "") or "")
        referencia = valores.get("REFERENCIA FABRICANTE") or str(
            registro.get("REFERENCIA_FABRICANTE", "") or "")

        descricao = self.validador.descricao(classe, sujeito.substantivo, valores,
                                             fabricante, referencia)
        un = self.validador.unidade(str(registro.get("UNIDADE_MEDIDA", "") or ""), classe)
        ncm = self.validador.ncm(registro.get("NCM", ""), classe)
        chave = self.validador.chave_identidade(classe, sujeito.substantivo, valores,
                                                fabricante, referencia)

        pendentes = [d.atributo for d in res.em_estado("PENDENTE")]
        conflitos = [d.atributo for d in res.em_estado(*ESTADOS_REVISAO)]
        # INVALIDO vira pendencia, nao revisao: a caixa esta vazia de todo jeito
        invalidos = [d.atributo for d in res.em_estado("INVALIDO")]

        if conflitos:
            estado = REVISAO
        elif pendentes or invalidos or chave is None:
            estado = PENDENTE
        else:
            estado = SANEADO
        self.contador[estado] += 1

        return RegistroSaneado(
            codigo=codigo, estado=estado, id_pdm=classe.id_pdm,
            substantivo=sujeito.substantivo, qualificador=sujeito.qualificador, grupo=grupo,
            confianca_sujeito=sujeito.confianca, empate_sujeito=sujeito.empate,
            grupo_corrigido=sujeito.grupo_corrigido,
            descricao_original=original, descricao_pdm=descricao,
            descricao_curta=self.validador.descricao_curta(descricao),
            unidade_original=str(registro.get("UNIDADE_MEDIDA", "") or ""),
            unidade_pdm=un.valor, unidade_motivo=un.motivo,
            ncm_original=str(registro.get("NCM", "") or ""),
            ncm_pdm=ncm.valor, ncm_motivo=ncm.motivo,
            chave_identidade=chave, completude=res.completude, discordancia=res.discordancia,
            escalado=escalado, motivos_escalada=res.motivos_escalada,
            pendentes=sorted(set(pendentes) | set(invalidos)),
            conflitos=conflitos, decisoes=res.decisoes,
        )

    # ------------------------------------------------------------- lote

    def processar_lote(self, registros: list[dict], log_cada: int = 2000) -> list[RegistroSaneado]:
        out = []
        for i, r in enumerate(registros, 1):
            out.append(self.processar(r))
            if log_cada and i % log_cada == 0:
                c = self.contador
                print(f"  {i}/{len(registros)}  saneado={c[SANEADO]} pendente={c[PENDENTE]} "
                      f"revisao={c[REVISAO]} fora={c[FORA_DO_PDM]} escalados={c['escalados']}",
                      flush=True)
        return out
