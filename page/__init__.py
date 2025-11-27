from sqlalchemy import text


def _get_table_columns(engine, table_name: str) -> set:
    """Retorna o conjunto de colunas existentes para uma tabela (lowercase)."""
    try:
        with engine.connect() as conn:
            q = text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = :tname
                """
            )
            rows = conn.execute(q, {"tname": table_name.lower()}).fetchall()
            return {r[0] for r in rows}
    except Exception:
        return set()


def resolve_table_column(
    engine, table: str, candidates: list, default: str | None = None
) -> str | None:
    """Retorna a primeira coluna existente na tabela dentre os candidatos.

    Se nenhuma for encontrada, retorna default.
    """
    cols = _get_table_columns(engine, table)
    for name in candidates:
        if name in cols:
            return name
    return default


def has_table_column(engine, table: str, column: str) -> bool:
    return column in _get_table_columns(engine, table)


def resolve_ofertas_codigo_col(engine) -> str:
    """Resolve qual coluna de código existe na tabela ofertas.

    Preferência: 'codigo_interno' > 'cod_interno' > 'codigo'.
    """
    col = resolve_table_column(
        engine,
        "ofertas",
        ["codigo_interno", "cod_interno", "codigo"],
        default="codigo_interno",
    )
    return col or "codigo_interno"


def resolve_mix_codigo_col(engine) -> str:
    return (
        resolve_table_column(
            engine,
            "mix_produtos",
            ["codigo_interno", "cod_interno", "codigo"],
            default="codigo_interno",
        )
        or "codigo_interno"
    )


def resolve_mix_descricao_col(engine) -> str:
    return (
        resolve_table_column(
            engine,
            "mix_produtos",
            ["descricao", "produto", "nome_produto"],
            default="descricao",
        )
        or "descricao"
    )


def resolve_mix_emb_col(engine) -> str | None:
    return resolve_table_column(
        engine, "mix_produtos", ["embseparacao", "emb_separacao"], default=None
    )


def resolve_pedidos_codigo_col(engine) -> str:
    return (
        resolve_table_column(
            engine,
            "pedidos_consolidados",
            ["codigo_interno", "cod_interno", "codigo"],
            default="codigo_interno",
        )
        or "codigo_interno"
    )


def resolve_pedidos_descricao_col(engine) -> str:
    return (
        resolve_table_column(
            engine,
            "pedidos_consolidados",
            ["descricao", "produto", "nome_produto"],
            default="descricao",
        )
        or "descricao"
    )


def resolve_pedidos_emb_col(engine) -> str | None:
    return resolve_table_column(
        engine,
        "pedidos_consolidados",
        ["embseparacao", "emb_separacao"],
        default=None,
    )
