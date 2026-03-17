from pathlib import Path

import numpy as np
import pandas as pd


def skill_carregar_e_sanitizar(caminho):
    """Carrega CSV ou Excel e aplica sanitizacao estrutural basica."""
    try:
        path = Path(caminho)
        extensao = path.suffix.lower()

        if extensao == ".csv":
            df = pd.read_csv(path, sep=None, engine="python", encoding="utf-8-sig")
        elif extensao in [".xlsx", ".xls"]:
            df = pd.read_excel(path, engine="openpyxl")
        else:
            return {"status": "erro", "mensagem": f"Extensao {extensao} nao suportada."}

        novas_colunas = []
        for col in df.columns:
            if ":" in str(col):
                partes_nome = str(col).split(":", 1)
                nome_col1, nome_col2 = partes_nome[0], partes_nome[1]
                split_data = df[col].astype(str).str.split(":", n=1, expand=True)
                if split_data.shape[1] == 1:
                    split_data[1] = np.nan
                df[nome_col1] = split_data[0]
                df[nome_col2] = split_data[1]
                novas_colunas.extend([nome_col1, nome_col2])
                df = df.drop(columns=[col])
            else:
                novas_colunas.append(col)

        df = df[novas_colunas]
        df = df.dropna(how="all")
        df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
        df.columns = [str(col).strip().lower().replace(" ", "_").replace(".", "_") for col in df.columns]

        return {
            "status": "sucesso",
            "formato": extensao,
            "total_linhas": len(df),
            "colunas_padronizadas": list(df.columns),
            "amostra": df.head(5).to_dict(orient="records"),
        }
    except Exception as exc:
        return {"status": "erro", "mensagem": f"Falha ao processar {caminho}: {exc}"}