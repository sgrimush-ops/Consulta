import os

import pandas as pd


def limpar_e_formatar_csv(input_path, output_path=None):
    """Padroniza CSVs com foco em governanca de dados do varejo."""
    try:
        df = pd.read_csv(input_path, sep=None, engine="python", encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(input_path, sep=None, engine="python", encoding="latin1")

    cols_para_dividir = []
    for col in df.columns:
        if df[col].dtype == "object" and df[col].astype(str).str.contains(":", regex=False).any():
            cols_para_dividir.append(col)

    for col in cols_para_dividir:
        nova_df = df[col].astype(str).str.split(":", expand=True)
        novos_nomes = [f"{col}_{i + 1}" for i in range(nova_df.shape[1])]
        df[novos_nomes] = nova_df
        df.drop(columns=[col], inplace=True)

    if not output_path:
        base, _ = os.path.splitext(input_path)
        output_path = f"{base}_limpo.csv"

    df.to_csv(output_path, sep=";", index=False, encoding="utf-8-sig")
    return output_path


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        print(limpar_e_formatar_csv(sys.argv[1]))
    else:
        print("Uso: python limpeza_dados.py <caminho_do_arquivo>")