"""Linha de comando: python -m app.cli <comando>

  migrar      aplica as migrações
  ingerir     publica o PDM, importa a tabela oficial da NCM, a base e os pedidos
  contagens   confere os totais contra a origem
  estruturar  lê classe e atributos de cada material (--etapa regras|llm)
  relatorio   mede a cobertura da estruturação
  avaliar     mede precisão do LLM contra gabarito derivado da base
  avaliar-sugestoes   mede se a opção certa aparece entre as sugestões (base inteira)
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import text

from .config import RAIZ_BACKEND, settings


def _migrar() -> None:
    from alembic import command
    from alembic.config import Config

    from .db import engine

    cfg = Config(str(RAIZ_BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ_BACKEND / "migrations"))
    cfg.attributes["url"] = engine().url.render_as_string(hide_password=False)
    command.upgrade(cfg, "head")
    print("migrações aplicadas")


def _ingerir(args) -> None:
    from . import ingestao
    from .db import transacao
    from .ncm import tabela
    from .pdm import repositorio

    s = settings()
    with transacao() as c:
        v = repositorio.publica(c, s.pdm_xlsx)
        print(f"PDM publicado: versão {v}")
    cache = RAIZ_BACKEND / "artefatos" / "ncm_siscomex.json"
    if args.baixar_ncm or not cache.exists():
        print("baixando a tabela oficial da NCM (Siscomex)...")
        tabela.baixa(cache)
    with transacao() as c:
        print(f"tabela NCM importada: versão {tabela.importa(c, cache)}")
        print(f"base: {ingestao.importa_base(c, s.base_xlsx)} materiais")
        print(f"pedidos: {ingestao.importa_pedidos(c, s.pedidos_xlsx)}")
        ingestao.semeia_equivalencias(c)


def _contagens() -> None:
    from .db import engine

    with engine().connect() as c:
        for t in ("pdm_versao", "ncm_tabela", "material", "pedido", "equivalencia"):
            print(f"{t:14s}{c.execute(text(f'select count(*) from {t}')).scalar():>8}")
        print("pdm ativo:", c.execute(text("select conteudo->'classes' is not null from pdm_versao where ativa")).scalar())


def _estruturar(args) -> None:
    from .estruturacao import executor

    if args.etapa == "regras":
        print(executor.etapa_regras(args.limite))
    else:
        from .estruturacao import etapa_llm

        if args.tudo:
            print(etapa_llm.executa_tudo(teto_usd=args.teto_usd, modelo=args.modelo))
        else:
            print(etapa_llm.executa(limite=args.limite, modelo=args.modelo, amostra=args.amostra))


def _avaliar(args) -> None:
    import json

    from .estruturacao import avaliar

    print(json.dumps(avaliar.avaliar(args.n, modelo=args.modelo), ensure_ascii=False, indent=2))


def _avaliar_sugestoes(args) -> None:
    import json

    from .sugestoes import avaliar

    print(json.dumps(avaliar.avalia(args.n), ensure_ascii=False, indent=2))


def _relatorio() -> None:
    from .estruturacao import relatorio

    relatorio.imprime()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="app.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrar")
    i = sub.add_parser("ingerir")
    i.add_argument("--baixar-ncm", action="store_true", help="baixa a tabela da NCM mesmo com cópia local")
    sub.add_parser("contagens")
    e = sub.add_parser("estruturar")
    e.add_argument("--etapa", choices=["regras", "llm"], default="regras")
    e.add_argument("--limite", type=int)
    e.add_argument("--modelo")
    e.add_argument("--amostra", action="store_true", help="llm: só uma amostra aleatória, para medir custo e acerto")
    e.add_argument("--tudo", action="store_true", help="llm: todos os candidatos, em lotes, com teto de gasto")
    e.add_argument("--teto-usd", type=float, default=60.0, help="llm --tudo: para ao passar deste gasto estimado")
    sub.add_parser("relatorio")
    sg = sub.add_parser("avaliar-sugestoes")
    sg.add_argument("-n", type=int, default=1500)
    av = sub.add_parser("avaliar")
    av.add_argument("-n", type=int, default=120)
    av.add_argument("--modelo")
    args = ap.parse_args(argv)
    {"migrar": lambda: _migrar(), "ingerir": lambda: _ingerir(args), "contagens": lambda: _contagens(),
     "estruturar": lambda: _estruturar(args), "relatorio": lambda: _relatorio(), "avaliar": lambda: _avaliar(args), "avaliar-sugestoes": lambda: _avaliar_sugestoes(args)}[args.cmd]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
