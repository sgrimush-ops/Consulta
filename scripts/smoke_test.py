#!/usr/bin/env python3
"""
Smoke tests automatizados para páginas Streamlit sem UI real.

O teste stubba o módulo `streamlit`, importa as páginas e exercita:
- Resolvers de colunas em `page/__init__.py`
- Conversão de tipos em `aprovacao_pedidos.formatar_tipos_df`
- Funções de limpeza em `ver_ofertas` (retornam 0 em ambientes sem DB)

Uso:
  /workspaces/ProjetoBak/.venv/bin/python scripts/smoke_test.py
Retorno:
  Código 0 em sucesso; >0 em falhas.
"""

from __future__ import annotations

import sys
import os
import types
import traceback


class _StreamlitStub:
    def __init__(self):
        # column_config stubs
        self.column_config = types.SimpleNamespace(
            NumberColumn=lambda *a, **k: None,
            TextColumn=lambda *a, **k: None,
            DateColumn=lambda *a, **k: None,
            CheckboxColumn=lambda *a, **k: None,
        )
        # session_state stub
        self.session_state = {}

    def __getattr__(self, name):
        # cache_data decorator → identidade
        if name == "cache_data":
            def deco(*dargs, **dkwargs):
                def wrapper(func):
                    return func
                return wrapper
            return deco

        # st.stop / st.rerun como no-op
        if name in {"stop", "rerun"}:
            def _no_op(*a, **k):
                return None
            return _no_op

        # Demais funções: no-op
        def _f(*a, **k):
            return None

        return _f


def _install_streamlit_stub():
    sys.modules["streamlit"] = _StreamlitStub()


def main() -> int:
    try:
        # Garantir que o diretório do projeto esteja no PYTHONPATH
        repo_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..")
        )
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)

        _install_streamlit_stub()

        # Imports de páginas
        import importlib

        modules = [
            "page.__init__",
            "page.home",
            "page.consulta_cd",
            "page.ver_ofertas",
            "page.pedido_cd",
            "page.gestao_promo",
            "page.aprovacao_pedidos",
        ]

        for m in modules:
            importlib.import_module(m)
            print(f"import_ok {m}")

        # Exercitar resolvers com SQLite (retornam defaults)
        from sqlalchemy import create_engine
        engine = create_engine("sqlite:///:memory:")
        from page import (
            resolve_ofertas_codigo_col,
            resolve_mix_codigo_col,
            resolve_mix_descricao_col,
            resolve_mix_emb_col,
            resolve_pedidos_codigo_col,
            resolve_pedidos_descricao_col,
            resolve_pedidos_emb_col,
        )

        assert resolve_ofertas_codigo_col(engine) == "codigo_interno"
        assert resolve_mix_codigo_col(engine) == "codigo_interno"
        assert resolve_mix_descricao_col(engine) == "descricao"
        assert resolve_mix_emb_col(engine) == "embalagem"
        assert resolve_pedidos_codigo_col(engine) == "codigo_interno"
        assert resolve_pedidos_descricao_col(engine) == "descricao"
        assert resolve_pedidos_emb_col(engine) == "embalagem"
        print("resolvers_ok")

        # Teste de conversão de tipos em aprovacao_pedidos
        import pandas as pd
        from page.aprovacao_pedidos import formatar_tipos_df

        df = pd.DataFrame(
            {
                "loja_001": ["1", "2"],
                "loja_002": ["0", None],
                "total_cx": ["3", "4"],
                "embalagem": ["5", "6"],
                "codigo_interno": ["123", "456"],
            }
        )
        res = formatar_tipos_df(df)
        assert str(res["loja_001"].dtype) == "int64"
        assert str(res["total_cx"].dtype) == "int64"
        assert str(res["embalagem"].dtype) == "int64"
        assert str(res["codigo_interno"].dtype) == "int64"
        print("format_ok")

        # Funções de limpeza em ver_ofertas: devem ser tolerantes (retornar 0)
        from page.ver_ofertas import (
            cleanup_old_ofertas,
            cleanup_old_pedidos_aprovados,
        )

        assert isinstance(cleanup_old_ofertas(engine, 1), int)
        assert isinstance(cleanup_old_pedidos_aprovados(engine, 7), int)
        print("cleanup_ok")

        print("SMOKE_ALL_OK")
        return 0
    except Exception:
        traceback.print_exc()
        print("SMOKE_FAILED")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
