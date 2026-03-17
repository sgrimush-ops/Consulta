import pandas as pd
import sys
import os

def limpar_e_formatar_csv(input_path, output_path=None):
    """
    Realiza a limpeza e padronização de arquivos CSV conforme regras de governança.
    """
    print(f"Lendo arquivo: {input_path}")
    
    # Tenta ler com diferentes encodings comuns em ambientes brasileiros
    try:
        df = pd.read_csv(input_path, sep=None, engine='python', encoding='utf-8')
    except:
        df = pd.read_csv(input_path, sep=None, engine='python', encoding='latin1')

    # Regra: Procurar colunas que contenham ':' e dividi-las
    cols_para_dividir = []
    for col in df.columns:
        if df[col].dtype == 'object' and df[col].str.contains(':').any():
            cols_para_dividir.append(col)
    
    for col in cols_para_dividir:
        print(f"Dividindo coluna '{col}' baseada no delimitador ':'")
        nova_df = df[col].str.split(':', expand=True)
        # Nomeia as novas colunas
        novos_nomes = [f"{col}_{i+1}" for i in range(nova_df.shape[1])]
        df[novos_nomes] = nova_df
        df.drop(columns=[col], inplace=True)

    # Garante que números sejam tratados corretamente (se necessário)
    # df = df.apply(lambda x: x.str.replace(',', '.') if x.dtype == "object" else x)

    if not output_path:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_limpo.csv"

    # Salva no padrão da governança: ';' e UTF-8
    df.to_csv(output_path, sep=';', index=False, encoding='utf-8-sig')
    print(f"Arquivo limpo salvo em: {output_path}")
    return output_path

if __name__ == "__main__":
    if len(sys.argv) > 1:
        limpar_e_formatar_csv(sys.argv[1])
    else:
        print("Uso: python limpeza_dados.py <caminho_do_arquivo>")
