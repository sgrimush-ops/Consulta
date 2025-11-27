from sqlalchemy import text


def resolve_ofertas_codigo_col(engine) -> str:
    """Resolve qual coluna de código existe na tabela ofertas.

    Retorna em ordem de preferência: 'codigo_interno', 'cod_interno', 'codigo'.
    """
    try:
        with engine.connect() as conn:
            q = text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'ofertas'
                  AND column_name IN ('codigo_interno','cod_interno','codigo')
                """
            )
            cols = {row[0] for row in conn.execute(q)}
        for name in ("codigo_interno", "cod_interno", "codigo"):
            if name in cols:
                return name
    except Exception:
        pass
    return "codigo_interno"
