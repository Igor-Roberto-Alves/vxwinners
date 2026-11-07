"""Contrato da API. O OpenAPI gerado a partir destes modelos é a fonte dos tipos do frontend."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ------------------------------------------------------------------ respostas
class CampoView(BaseModel):
    atributo: str
    ordem: int
    obrigatorio: bool
    aplica: bool | None = Field(None, description="false: não vale para este item; null: depende de outro atributo ainda vazio")
    condicao: str | None = None
    tipo: str
    formato: str
    valores_permitidos: list[str]
    valor: str | None = None
    origem: str | None = Field(None, description="DIGITADO, OPCAO, PEDIDO_REGRA, PEDIDO_LLM...")
    trecho: str | None = None
    valido: bool | None = Field(None, description="false: fora do PDM; vira exceção na aprovação")
    motivo: str | None = None
    candidatos: list[str] = []


class ClasseView(BaseModel):
    id_pdm: str
    nome: str | None
    nomes_possiveis: list[str]
    grupo: str
    grupo_descricao: str | None
    criterio_identidade: str
    confirmada: bool


class CampoFiscal(BaseModel):
    padrao: str | None = None
    usado: str | None = None
    personalizado: bool = False


class NcmView(BaseModel):
    esperado: str | None
    regra: str
    usado: str | None
    personalizado: bool
    validacao: dict[str, Any] | None


class FiscalView(BaseModel):
    unidade: CampoFiscal
    grupo: CampoFiscal
    ncm: NcmView


class DescricaoView(BaseModel):
    longa: str | None
    curta: str | None
    curta_tamanho: int
    curta_limite: int


class ChaveView(BaseModel):
    texto: str | None
    completa: bool
    faltando: list[str]


class BloqueioView(BaseModel):
    codigo: str
    mensagem: str
    atributo: str | None = None
    sucessores: list[str] | None = None


class ExcecaoPrevista(BaseModel):
    id: str = Field(description="chave a usar em `justificativas` na aprovação")
    tipo: str
    atributo: str | None
    padrao: str | None
    usado: str | None
    exige_revisor: bool


class CandidatoView(BaseModel):
    codigo: str
    nivel: Literal["IGUAL", "PROVAVEL", "DIVERGENTE", "PARECIDO", "EQUIVALENTE"]
    pontos: float
    origem: str
    status: str | None
    centro: str | None
    estoque: float | None
    descricao: str | None
    comparacao: list[dict[str, Any]]
    motivo: str
    permite_uso_direto: bool


class DuplicidadeView(BaseModel):
    candidatos: list[CandidatoView]
    comparaveis: int = Field(description="registros da classe comparáveis por atributos")
    total_classe: int


class CadastroView(BaseModel):
    id: str
    estado: str
    versao: int
    pedido_id: str | None
    analista: str | None
    pdm_versao_id: int | None
    classe: ClasseView | None
    proposta_de_classe: dict[str, Any] | None
    campos: list[CampoView]
    fiscal: FiscalView | None
    fabricante: str | None
    referencia_fabricante: str | None
    centro: str | None
    descricao: DescricaoView
    chave: ChaveView | None
    bloqueios: list[BloqueioView]
    excecoes_previstas: list[ExcecaoPrevista]
    avisos: list[str]
    pronto_para_aprovar: bool
    codigo_erp: str | None
    usar_codigo: str | None
    motivo: str | None
    duplicidade: DuplicidadeView | None
    resumo_leitura: dict[str, Any] | None
    texto_inicial: str | None = Field(None, description="texto de onde o rascunho partiu; serve para reler ao trocar de classe")
    interpretacao: dict[str, Any] | None = None
    devolucao: dict[str, Any] | None = None
    llm: dict[str, Any] | None = None


class OpcaoView(BaseModel):
    valor: str
    n: int
    pct: float | None
    fonte: str


class SugestoesView(BaseModel):
    atributo: str
    opcoes: list[OpcaoView]
    base: int
    contexto: list[str]
    sem_opcoes_motivo: str | None
    valores_permitidos: list[str]


class SugestaoClasse(BaseModel):
    nome: str
    id_pdm: str
    grupo: str
    grupo_descricao: str
    pontos: float
    resto: list[str]


class NomesView(BaseModel):
    consulta: str
    ambiguo: bool = Field(description="a consulta casa nomes de mais de uma classe: a pessoa precisa escolher")
    itens: list[SugestaoClasse]
    fora_do_pdm: bool = Field(description="nada casou: o material pode estar fora do PDM (recusar ou propor classe)")


# ------------------------------------------------------------------ pedidos de entrada
class AtributoView(BaseModel):
    nome: str
    ordem: int
    obrigatorio: bool
    condicao: str | None
    tipo: str
    formato: str
    valores_permitidos: list[str]


class ClassePdmView(BaseModel):
    id_pdm: str
    nomes: list[str]
    grupo: str
    unidade_padrao: str
    criterio_identidade: str
    atributos: list[AtributoView]


class PedidoView(BaseModel):
    id: str
    data_solicitacao: str | None
    centro: str | None
    area: str | None
    canal: str | None
    urgencia: str | None
    texto: str | None
    tipo_anexo: str | None
    tem_anexo: bool
    estado: str
    analista: str | None


class PaginaPedidos(BaseModel):
    total: int
    itens: list[PedidoView]


class PedidoDetalhe(PedidoView):
    conteudo_anexo: str | None = None


class PerguntaView(BaseModel):
    id: int
    destinatario: str | None
    pergunta: str
    resposta: str | None
    enviada_em: str | None
    respondida_em: str | None


class ResumoView(BaseModel):
    pedidos: dict[str, int] = Field(description="pedidos por estado")
    cadastros: dict[str, int] = Field(description="cadastros por estado")
    excecoes_pendentes: int = Field(description="cadastros aguardando o segundo analista")


class TrechoLido(BaseModel):
    atributo: str
    valor: str
    trecho: str | None


class BuscaView(BaseModel):
    consulta: str
    classe: ClasseView | None
    campos: list[CampoView]
    interpretacao: list[TrechoLido] = Field(description="o que foi lido do texto; a pessoa confere antes de usar")
    descricao: DescricaoView
    chave: ChaveView | None
    duplicidade: DuplicidadeView | None
    fabricante: str | None
    referencia_fabricante: str | None
    alternativas: list[SugestaoClasse]
    ambiguo: bool
    fora_do_pdm: bool


# ------------------------------------------------------------------ requisições
class NovoCadastro(BaseModel):
    id_pdm: str | None = None
    nome: str | None = None
    texto: str | None = Field(None, description="texto livre inicial (guardado para auditoria)")
    centro: str | None = None
    pedido_id: str | None = Field(None, description="cria o rascunho lendo este pedido")


class Edicao(BaseModel):
    versao: int = Field(description="versão que o cliente viu; evita sobrescrever a edição de outra pessoa")
    classe: dict[str, str | None] | None = Field(None, description='{"id_pdm": "...", "nome": "..."}: confirma a classe')
    valores: dict[str, str | dict[str, str] | None] | None = Field(
        None, description='atributo → texto, ou {"valor": "...", "origem": "OPCAO"}; null/vazio remove')
    campos: dict[str, str | None] | None = Field(None, description="unidade, grupo, ncm, fabricante, referencia_fabricante, centro")


class Interpretar(BaseModel):
    versao: int
    texto: str = Field(min_length=1, max_length=2000)


class UsarExistente(BaseModel):
    codigo: str
    justificativa: str | None = Field(None, description="obrigatória (mín. 10 caracteres) se o código diverge do rascunho em atributo de identidade")


class Busca(BaseModel):
    texto: str = Field(min_length=1, max_length=2000)
    id_pdm: str | None = Field(None, description="classe escolhida pela pessoa; vazio: usa a classe lida do texto, como proposta")
    nome: str | None = None
    valores: dict[str, str | None] | None = Field(None, description="atributo → valor refinado pela pessoa; substitui o lido do texto")


class Reativar(BaseModel):
    codigo: str
    justificativa: str


class Devolver(BaseModel):
    pergunta: str | None = Field(None, description="vazio: o sistema lista os obrigatórios que faltam")


class Responder(BaseModel):
    pergunta_id: int
    resposta: str = Field(min_length=1)


class Aprovar(BaseModel):
    versao: int
    justificativas: dict[str, str] = Field(default_factory=dict, description="id da exceção → justificativa (mín. 10 caracteres)")


class Recusar(BaseModel):
    motivo: str


class ProporClasse(BaseModel):
    nome_sugerido: str
    justificativa: str
    atributos_sugeridos: list[str] = []


class Revisao(BaseModel):
    aprovar: bool
    comentario: str | None = None


class Cancelar(BaseModel):
    motivo: str | None = None


class DecisaoProposta(BaseModel):
    aceita: bool
    comentario: str | None = None


class PedidoEntrada(BaseModel):
    id: str
    data_solicitacao: str | None = None
    centro: str | None = None
    area: str | None = None
    canal: str | None = None
    urgencia: str | None = None
    texto: str
    tipo_anexo: str | None = None
    conteudo_anexo: str | None = None


class ImportaPedidos(BaseModel):
    pedidos: list[PedidoEntrada] = Field(min_length=1, max_length=5000)
