"""Configuração por variáveis de ambiente. Segredos nunca entram no repositório."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ_BACKEND = Path(__file__).resolve().parent.parent
RAIZ_REPO = RAIZ_BACKEND.parent
# Em desenvolvimento o .env fica um nível acima do repositório (fora do git).
ARQUIVOS_ENV = (RAIZ_BACKEND / ".env", RAIZ_REPO / ".env", RAIZ_REPO.parent / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=[str(p) for p in ARQUIVOS_ENV], extra="ignore")

    # Banco. Sem valor, o desenvolvimento sobe um PostgreSQL embutido (app.devdb).
    database_url: str | None = None
    database_nome: str = "cadastro"

    # PDM de origem (planilha). A versão ativa mora no banco.
    pdm_xlsx: Path = RAIZ_REPO / "dados" / "03_padrao_cadastro_PDM.xlsx"
    base_xlsx: Path = RAIZ_REPO / "dados" / "01_base_materiais.xlsx"
    pedidos_xlsx: Path = RAIZ_REPO / "dados" / "02_pedidos_cadastro.xlsx"

    # Autenticação. "dev" aceita cabeçalhos X-Usuario/X-Papel; "oidc" ainda não está implementado.
    auth_modo: str = "dev"

    # LLM. "bedrock" usa o AWS Bedrock; "aws_platform" usa o Claude Platform on AWS.
    llm_provider: str = "bedrock"
    llm_habilitado: bool = True
    aws_region: str | None = None
    aws_default_region: str = "us-east-1"
    anthropic_aws_workspace_id: str | None = None
    llm_modelo_extracao: str = "claude-haiku-5-5"
    llm_modelo_dificil: str = "claude-sonnet-5-5"
    llm_concorrencia: int = 8
    llm_timeout_s: float = 60.0

    # Conector ERP por arquivos.
    erp_dir_saida: Path = RAIZ_BACKEND / "erp_out"
    erp_dir_entrada: Path = RAIZ_BACKEND / "erp_in"

    @property
    def regiao(self) -> str:
        return self.aws_region or self.aws_default_region


@lru_cache
def settings() -> Settings:
    return Settings()
