"""Aplicação FastAPI: `uvicorn app.main:app`."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from .api.deps import conexao
from .api.rotas import router
from .api.rotas_sugestao import router as rotas_sugestao
from .cadastro.modelo import ErroNegocio
from .config import RAIZ_REPO, settings
from .db import engine
from .sugestoes import modelos

PROBLEM = "application/problem+json"


def _problema(status: int, titulo: str, detalhe: str, **extra) -> JSONResponse:
    return JSONResponse({"type": f"about:blank#{titulo}", "title": titulo, "status": status, "detail": detalhe, **extra},
                        status_code=status, media_type=PROBLEM)


def confere_migracoes() -> None:
    """Recusa subir com o banco desatualizado: melhor falhar na partida do que no meio de uma requisição."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    from .config import RAIZ_BACKEND

    cfg = Config(str(RAIZ_BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ_BACKEND / "migrations"))
    cabeca = ScriptDirectory.from_config(cfg).get_current_head()
    with engine().connect() as c:
        try:
            atual = c.execute(text("select version_num from alembic_version")).scalar()
        except Exception:  # noqa: BLE001 - tabela inexistente: banco virgem
            atual = None
    if atual != cabeca:
        raise RuntimeError(f"banco na versao {atual!r}, esperado {cabeca!r}: rode `python -m app.cli migrar` antes de subir a API")


def cria_app(verifica_migracoes: bool = True, carrega_modelos: bool = True) -> FastAPI:
    @asynccontextmanager
    async def ciclo(app: FastAPI):
        if settings().auth_modo != "dev":
            raise RuntimeError("AUTH_MODO diferente de 'dev' ainda nao e suportado: a autenticacao OIDC nao foi implementada")
        if verifica_migracoes:
            confere_migracoes()
        if carrega_modelos:
            modelos.carrega()   # opcional: sem modelos treinados o cadastro segue sem estas sugestões
        yield

    app = FastAPI(title="Cadastro de materiais", version="0.1.0", lifespan=ciclo,
                  description="Modo de cadastro: sugestão de classe e valores a partir do histórico, verificação de duplicidade, "
                              "exceções com justificativa e segundo analista.")
    origens = [o.strip() for o in settings().cors_origens.split(",") if o.strip()]
    if origens:
        app.add_middleware(CORSMiddleware, allow_origins=origens, allow_methods=["*"], allow_headers=["*"])

    @app.exception_handler(ErroNegocio)
    async def _negocio(_: Request, e: ErroNegocio):
        extra = {}
        if isinstance(e.detalhes, dict):
            extra = e.detalhes
        elif e.detalhes is not None:
            extra = {"detalhes": e.detalhes}
        return _problema(e.status, e.codigo, e.mensagem, **extra)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, e: StarletteHTTPException):
        return _problema(e.status_code, {401: "nao_autenticado", 403: "sem_permissao"}.get(e.status_code, "erro_http"), str(e.detail))

    @app.exception_handler(RequestValidationError)
    async def _validacao(_: Request, e: RequestValidationError):
        erros = [{"campo": ".".join(str(x) for x in er["loc"]), "mensagem": er["msg"]} for er in e.errors()]
        return _problema(422, "requisicao_invalida", "a requisicao tem campos invalidos", erros=erros)

    @app.get("/saude", tags=["infra"])
    def saude():
        with engine().connect() as c:
            c.execute(text("select 1"))
            versao = c.execute(text("select id from pdm_versao where ativa")).scalar()
        s = settings()
        return {"status": "ok", "pdm_versao": versao, "llm": {"provider": s.llm_provider, "habilitado": s.llm_habilitado},
                "modelos_sugestao": modelos.estado()}

    if settings().auth_modo == "dev":
        # Painel de desenvolvimento para ver o fluxo ao vivo. NÃO é o frontend do produto, que vem de outra branch.
        from pathlib import Path

        pagina = Path(__file__).parent / "painel" / "index.html"

        @app.get("/painel", include_in_schema=False)
        def painel():
            return FileResponse(pagina, media_type="text/html")

        # O frontend do time: casca em mockup_plataforma.html, cadastro real em frontend/
        @app.get("/", include_in_schema=False)
        def frontend():
            return FileResponse(RAIZ_REPO / "mockup_plataforma.html", media_type="text/html")

        @app.get("/mockup", include_in_schema=False)
        def mockup():
            return RedirectResponse("/", status_code=307)

        app.mount("/frontend", StaticFiles(directory=RAIZ_REPO / "frontend"), name="frontend")
        app.include_router(rotas_sugestao)

    app.include_router(router)
    return app


app = cria_app()
