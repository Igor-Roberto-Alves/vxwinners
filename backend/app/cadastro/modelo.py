"""Estados do cadastro, transições permitidas e erros de negócio (docs/04-plano-modo-cadastro.md, seção 3)."""
from __future__ import annotations

RASCUNHO = "RASCUNHO"
AGUARDANDO_SOLICITANTE = "AGUARDANDO_SOLICITANTE"
AGUARDANDO_CLASSE = "AGUARDANDO_CLASSE"
EM_REVISAO = "EM_REVISAO"
APROVADO = "APROVADO"
AGUARDANDO_REATIVACAO = "AGUARDANDO_REATIVACAO"
CADASTRADO = "CADASTRADO"
ERRO_ERP = "ERRO_ERP"
JA_EXISTE = "JA_EXISTE"
FORA_DO_PDM = "FORA_DO_PDM"
CANCELADO = "CANCELADO"

TRANSICOES: dict[str, set[str]] = {
    RASCUNHO: {AGUARDANDO_SOLICITANTE, AGUARDANDO_CLASSE, EM_REVISAO, APROVADO, JA_EXISTE, FORA_DO_PDM, CANCELADO},
    AGUARDANDO_SOLICITANTE: {RASCUNHO, CANCELADO},
    AGUARDANDO_CLASSE: {RASCUNHO, FORA_DO_PDM, CANCELADO},
    EM_REVISAO: {APROVADO, AGUARDANDO_REATIVACAO, RASCUNHO},
    APROVADO: {CADASTRADO, ERRO_ERP},
    AGUARDANDO_REATIVACAO: {JA_EXISTE, ERRO_ERP},
    ERRO_ERP: {APROVADO, AGUARDANDO_REATIVACAO},
    CADASTRADO: set(), JA_EXISTE: set(), FORA_DO_PDM: set(), CANCELADO: set(),
}
EDITAVEIS = {RASCUNHO}  # só em rascunho os dados mudam; depois disso, o histórico fica intacto

# Exceções: tipo → exige segundo analista? (docs/04, seção 7)
EXCECOES_EXIGEM_REVISOR = {
    "FORA_DA_LISTA": True, "FORMATO_FORA_DO_PDM": True, "UNIDADE_DIFERENTE_DO_PADRAO": True,
    "GRUPO_DIFERENTE_DO_PADRAO": True, "NCM_DIFERENTE_DA_REGRA": True,
    "DUPLICIDADE_IGUAL": True, "DUPLICIDADE_BLOQUEADO_IGUAL": True,
    "DUPLICIDADE_PROVAVEL": False,   # só justificativa
    "REATIVACAO": True,
}


class ErroNegocio(Exception):
    """Erro previsto, devolvido ao cliente como application/problem+json."""

    def __init__(self, codigo: str, mensagem: str, status: int = 422, detalhes: dict | list | None = None):
        super().__init__(mensagem)
        self.codigo, self.mensagem, self.status, self.detalhes = codigo, mensagem, status, detalhes


def exige_transicao(de: str, para: str) -> None:
    if para not in TRANSICOES.get(de, set()):
        raise ErroNegocio("transicao_invalida", f"nao e possivel passar de {de} para {para}", 409)
