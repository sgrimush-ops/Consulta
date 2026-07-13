from __future__ import annotations

import re
import unicodedata

from sqlalchemy import text


CONNECTOR_WORDS = {"de", "da", "do", "das", "dos"}
CARGOS_BOOTSTRAP_LOCK_KEY = 104729


def normalize_cargo_name(cargo: str | None) -> str:
    normalized = str(cargo or "").strip().lower()
    normalized = unicodedata.normalize("NFKD", normalized)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = re.sub(r"\s+", " ", normalized)
    tokens = [token for token in normalized.split(" ") if token and token not in CONNECTOR_WORDS]
    normalized = " ".join(tokens)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _lock_cargos_catalog(conn) -> None:
    dialect_name = getattr(getattr(conn, "dialect", None), "name", "")
    if dialect_name == "postgresql":
        conn.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": CARGOS_BOOTSTRAP_LOCK_KEY},
        )


def _ensure_cargos_catalog(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS cargos_catalogo (
                id SERIAL PRIMARY KEY,
                nome TEXT NOT NULL,
                criado_em TIMESTAMP NOT NULL DEFAULT NOW(),
                atualizado_em TIMESTAMP NOT NULL DEFAULT NOW()
            )
            """
        )
    )
    conn.execute(
        text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_cargos_catalogo_nome_normalizado
            ON cargos_catalogo ((LOWER(BTRIM(nome))))
            """
        )
    )


def ensure_cargos_catalog(engine, conn=None) -> None:
    if conn is not None:
        _ensure_cargos_catalog(conn)
        return

    with engine.begin() as conn:
        _lock_cargos_catalog(conn)
        _ensure_cargos_catalog(conn)


def _sync_cargos_from_existing(conn) -> None:
    user_rows = conn.execute(
        text(
            """
            SELECT DISTINCT cargo
            FROM users
            WHERE cargo IS NOT NULL AND BTRIM(cargo) <> ''
            """
        )
    ).fetchall()
    request_rows = conn.execute(
        text(
            """
            SELECT DISTINCT cargo
            FROM solicitacoes_acesso
            WHERE cargo IS NOT NULL AND BTRIM(cargo) <> ''
            """
        )
    ).fetchall()
    catalog_rows = conn.execute(
        text(
            """
            SELECT id, nome
            FROM cargos_catalogo
            ORDER BY id
            """
        )
    ).fetchall()

    existing_values = (
        [row[0] for row in user_rows]
        + [row[0] for row in request_rows]
        + ["consumo cd"]
    )
    canonical_names = []
    seen_names = set()
    for raw_value in existing_values:
        normalized = normalize_cargo_name(raw_value)
        if normalized and normalized not in seen_names:
            seen_names.add(normalized)
            canonical_names.append(normalized)

    keep_catalog_rows = {}
    duplicate_catalog_ids = []
    empty_catalog_ids = []
    for row in catalog_rows:
        normalized = normalize_cargo_name(row.nome)
        if not normalized:
            empty_catalog_ids.append(row.id)
            continue
        if normalized in keep_catalog_rows:
            duplicate_catalog_ids.append(row.id)
            continue
        keep_catalog_rows[normalized] = row.id

    conn.execute(
        text(
            """
            UPDATE users
            SET cargo = LOWER(BTRIM(cargo))
            WHERE cargo IS NOT NULL AND BTRIM(cargo) <> ''
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE solicitacoes_acesso
            SET cargo = LOWER(BTRIM(cargo))
            WHERE cargo IS NOT NULL AND BTRIM(cargo) <> ''
            """
        )
    )

    for raw_value in existing_values:
        normalized = normalize_cargo_name(raw_value)
        if not normalized:
            continue

        conn.execute(
            text(
                """
                UPDATE users
                SET cargo = :normalized
                WHERE cargo IS NOT NULL
                  AND LOWER(BTRIM(cargo)) = LOWER(BTRIM(:raw_value))
                """
            ),
            {"normalized": normalized, "raw_value": raw_value},
        )
        conn.execute(
            text(
                """
                UPDATE solicitacoes_acesso
                SET cargo = :normalized
                WHERE cargo IS NOT NULL
                  AND LOWER(BTRIM(cargo)) = LOWER(BTRIM(:raw_value))
                """
            ),
            {"normalized": normalized, "raw_value": raw_value},
        )

    if empty_catalog_ids:
        conn.execute(
            text("DELETE FROM cargos_catalogo WHERE id = ANY(:ids)"),
            {"ids": empty_catalog_ids},
        )

    if duplicate_catalog_ids:
        conn.execute(
            text("DELETE FROM cargos_catalogo WHERE id = ANY(:ids)"),
            {"ids": duplicate_catalog_ids},
        )

    for normalized, row_id in keep_catalog_rows.items():
        conn.execute(
            text(
                """
                UPDATE cargos_catalogo
                SET nome = :nome,
                    atualizado_em = NOW()
                WHERE id = :id
                """
            ),
            {"id": row_id, "nome": normalized},
        )

    for normalized in canonical_names:
        conn.execute(
            text(
                """
                INSERT INTO cargos_catalogo (nome)
                SELECT :nome
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM cargos_catalogo
                    WHERE LOWER(BTRIM(nome)) = LOWER(BTRIM(:nome))
                )
                """
            ),
            {"nome": normalized},
        )


def sync_cargos_from_existing(engine, conn=None) -> None:
    if conn is not None:
        _sync_cargos_from_existing(conn)
        return

    with engine.begin() as conn:
        _lock_cargos_catalog(conn)
        _ensure_cargos_catalog(conn)
        _sync_cargos_from_existing(conn)


def bootstrap_cargos_catalog(engine) -> None:
    with engine.begin() as conn:
        _lock_cargos_catalog(conn)
        _ensure_cargos_catalog(conn)
        _sync_cargos_from_existing(conn)


def list_cargos(engine) -> list[str]:
    bootstrap_cargos_catalog(engine)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT nome
                FROM cargos_catalogo
                ORDER BY nome
                """
            )
        ).fetchall()
    return [row[0] for row in rows]


def cargo_exists(engine, cargo: str | None) -> bool:
    normalized = normalize_cargo_name(cargo)
    if not normalized:
        return False

    bootstrap_cargos_catalog(engine)
    with engine.connect() as conn:
        return bool(
            conn.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM cargos_catalogo
                        WHERE LOWER(BTRIM(nome)) = LOWER(BTRIM(:cargo))
                    )
                    """
                ),
                {"cargo": normalized},
            ).scalar()
        )


def add_cargo(engine, cargo: str | None) -> tuple[bool, str]:
    normalized = normalize_cargo_name(cargo)
    if not normalized:
        return False, "Informe um cargo valido."

    bootstrap_cargos_catalog(engine)
    if cargo_exists(engine, normalized):
        return False, f"O cargo '{normalized}' ja existe na lista."

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO cargos_catalogo (nome, atualizado_em)
                VALUES (:nome, NOW())
                """
            ),
            {"nome": normalized},
        )

    return True, f"Cargo '{normalized}' adicionado com sucesso."


def rename_cargo(engine, current_name: str | None, new_name: str | None) -> tuple[bool, str]:
    current_normalized = normalize_cargo_name(current_name)
    new_normalized = normalize_cargo_name(new_name)

    if not current_normalized:
        return False, "Selecione um cargo para alterar."
    if not new_normalized:
        return False, "Informe o novo nome do cargo."
    if current_normalized == new_normalized:
        return False, "O novo nome do cargo e igual ao atual."

    bootstrap_cargos_catalog(engine)

    if not cargo_exists(engine, current_normalized):
        return False, f"O cargo '{current_normalized}' nao existe na lista."

    target_exists = cargo_exists(engine, new_normalized)

    params = {"current_name": current_normalized, "new_name": new_normalized}
    with engine.begin() as conn:
        if target_exists:
            # Quando o cargo de destino ja existe, fazemos fusao: migramos os
            # registros e removemos o cargo antigo do catalogo.
            conn.execute(
                text(
                    """
                    DELETE FROM cargos_catalogo
                    WHERE LOWER(BTRIM(nome)) = LOWER(BTRIM(:current_name))
                    """
                ),
                {"current_name": current_normalized},
            )
        else:
            conn.execute(
                text(
                    """
                    UPDATE cargos_catalogo
                    SET nome = :new_name,
                        atualizado_em = NOW()
                    WHERE LOWER(BTRIM(nome)) = LOWER(BTRIM(:current_name))
                    """
                ),
                params,
            )

        conn.execute(
            text(
                """
                UPDATE users
                SET cargo = :new_name
                WHERE cargo IS NOT NULL
                  AND LOWER(BTRIM(cargo)) = LOWER(BTRIM(:current_name))
                """
            ),
            params,
        )
        conn.execute(
            text(
                """
                UPDATE solicitacoes_acesso
                SET cargo = :new_name
                WHERE cargo IS NOT NULL
                  AND LOWER(BTRIM(cargo)) = LOWER(BTRIM(:current_name))
                """
            ),
            params,
        )

    if target_exists:
        return True, (
            f"Cargo '{current_normalized}' consolidado em '{new_normalized}' com sucesso."
        )

    return True, f"Cargo '{current_normalized}' renomeado para '{new_normalized}' com sucesso."


def get_cargo_normalization_preview(engine) -> list[dict[str, object]]:
    bootstrap_cargos_catalog(engine)

    with engine.connect() as conn:
        source_rows = conn.execute(
            text(
                """
                SELECT origem, cargo_informado, total_registros
                FROM (
                    SELECT
                        'Usuarios' AS origem,
                        cargo AS cargo_informado,
                        COUNT(*) AS total_registros
                    FROM users
                    WHERE cargo IS NOT NULL AND BTRIM(cargo) <> ''
                    GROUP BY cargo

                    UNION ALL

                    SELECT
                        'Solicitacoes' AS origem,
                        cargo AS cargo_informado,
                        COUNT(*) AS total_registros
                    FROM solicitacoes_acesso
                    WHERE cargo IS NOT NULL AND BTRIM(cargo) <> ''
                    GROUP BY cargo
                ) cargos_origem
                ORDER BY LOWER(BTRIM(cargo_informado)), origem
                """
            )
        ).fetchall()
        catalog_rows = conn.execute(
            text(
                """
                SELECT nome
                FROM cargos_catalogo
                """
            )
        ).fetchall()

    catalog_set = {normalize_cargo_name(row[0]) for row in catalog_rows}

    preview = []
    for row in source_rows:
        original = str(row.cargo_informado or "").strip()
        canonical = normalize_cargo_name(original)
        if not canonical:
            continue

        preview.append(
            {
                "Origem": row.origem,
                "Cargo Informado": original,
                "Cargo Canonico": canonical,
                "Total Registros": int(row.total_registros or 0),
                "Ja Catalogado": "Sim" if canonical in catalog_set else "Nao",
                "Mudou na Normalizacao": "Sim"
                if canonical != re.sub(r"\s+", " ", original.lower()).strip()
                else "Nao",
            }
        )

    return preview


def is_user_consumo_cd(engine=None, session_state=None) -> bool:
    """Verifica se o usuário atual possui cargo ou role 'consumo cd'."""
    if session_state is None:
        try:
            import streamlit as st
            session_state = st.session_state
        except Exception:
            return False

    role = str(session_state.get("role", "")).strip().lower()
    if role == "admin":
        return False

    cargo = str(session_state.get("cargo", "")).strip().lower()

    if not cargo and engine is not None:
        username = session_state.get("username")
        if username:
            try:
                with engine.connect() as conn:
                    result = conn.execute(
                        text("SELECT cargo FROM users WHERE LOWER(username) = :u"),
                        {"u": str(username).strip().lower()},
                    ).scalar()
                    if result:
                        cargo = str(result).strip().lower()
                        session_state["cargo"] = cargo
            except Exception:
                pass

    role_norm = normalize_cargo_name(role)
    cargo_norm = normalize_cargo_name(cargo)
    return "consumo cd" in cargo_norm or "consumo cd" in role_norm