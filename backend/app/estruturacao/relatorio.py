"""Mede a cobertura da estruturação. Os números saem do banco, nunca de estimativa."""
from __future__ import annotations

from sqlalchemy import text

from ..db import engine


def _q(c, sql, **kw):
    return c.execute(text(sql), kw).all()


def imprime() -> None:
    with engine().connect() as c:
        total = _q(c, "select count(*) from material")[0][0]
        proc = _q(c, "select count(*) from material_classificacao")[0][0]
        print(f"materiais: {total} | processados: {proc}")
        print("\nclasse resolvida, por método:")
        for met, n, com in _q(c, "select metodo, count(*), count(id_pdm) from material_classificacao group by 1 order by 2 desc"):
            print(f"  {met:12s} registros={n:6d}  com classe={com:6d} ({100*com/max(n,1):.1f}%)")
        com_classe = _q(c, "select count(*) from material_classificacao where id_pdm is not null")[0][0]
        print(f"\ncom classe: {com_classe} ({100*com_classe/total:.1f}% da base)")
        coerente = _q(c, """select count(*) from material_classificacao k join material m using (codigo)
            where k.id_pdm is not null and (select (conteudo->'classes'->k.id_pdm->>'grupo') from pdm_versao where ativa) = m.grupo""")[0][0]
        print(f"  grupo da classe = grupo do ERP: {coerente} ({100*coerente/max(com_classe,1):.1f}% das classificadas)")

        print("\nchave de identidade fechada (valores de alta confiança):")
        for crit, n, comp in _q(c, """select (select conteudo->'classes'->i.id_pdm->>'criterio' from pdm_versao where ativa) as crit,
               count(*), count(*) filter (where completa) from material_identidade i group by 1 order by 1"""):
            print(f"  {crit or '?':14s} classificados={n:6d}  chave completa={comp:6d} ({100*comp/max(n,1):.1f}%)")
        comp_total = _q(c, "select count(*) from material_identidade where completa")[0][0]
        print(f"  total com chave completa: {comp_total} ({100*comp_total/total:.1f}% da base)")
        grupos = _q(c, """select count(*), sum(n-1) from (select chave, count(*) n from material_identidade
                 where completa group by chave having count(*) > 1) t""")[0]
        print(f"  chaves com mais de um código: {grupos[0] or 0} | códigos redundantes: {grupos[1] or 0}")

        print("\natributos por origem (valores validados):")
        for o, n in _q(c, "select origem, count(*) from material_atributo where valor is not null group by 1 order by 2 desc"):
            print(f"  {o:14s}{n:8d}")
        print("\ncompleto por grupo (todos os obrigatórios de alta confiança):")
        for g, tot, comp in _q(c, """select m.grupo, count(*), count(*) filter (where i.completa)
               from material m left join material_identidade i using (codigo) group by 1 order by 2 desc"""):
            print(f"  {g:6s} total={tot:6d}  chave completa={comp:6d} ({100*comp/max(tot,1):.1f}%)")
