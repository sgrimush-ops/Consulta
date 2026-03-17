import pandas as pd
from pathlib import Path
from typing import Dict, Any, List
import numpy as np

def skill_carregar_e_sanitizar(caminho: str) -> Dict[str, Any]:
    """
    Lê CSV ou Excel (openpyxl) e aplica tratamentos base:
    - Identificação automática de formato.
    - Remoção de linhas 100% vazias.
    - Limpeza de colunas fantasmas (Unnamed).
    - Padronização de cabeçalhos para snake_case.
    """
    try:
        p = Path(caminho)
        extensao = p.suffix.lower()
        
        # 1. Leitura Híbrida (Regra 4 do Manual)
        if extensao == '.csv':
            df = pd.read_csv(p, sep=None, engine='python', encoding='utf-8-sig')
        elif extensao in ['.xlsx', '.xls']:
            df = pd.read_excel(p, engine='openpyxl')
        else:
            return {"status": "erro", "mensagem": f"Extensão {extensao} não suportada."}

        # 1.1 Split de Colunas com ':' (Nova Funcionalidade)
        novas_colunas = []
        for col in df.columns:
            if ":" in str(col):
                # Divide o nome da coluna
                partes_nome = str(col).split(":", 1)
                nome_col1, nome_col2 = partes_nome[0], partes_nome[1]
                
                # Divide o conteúdo da coluna
                # Garante que a coluna seja string para o split
                split_data = df[col].astype(str).str.split(":", n=1, expand=True)
                
                # Se o split resultou em apenas uma coluna (não achou ':' no dado)
                if split_data.shape[1] == 1:
                    split_data[1] = np.nan
                
                df_col1 = split_data[0]
                df_col2 = split_data[1]
                
                # Adiciona as novas colunas à lista temporária para reconstrução
                df[nome_col1] = df_col1
                df[nome_col2] = df_col2
                
                novas_colunas.extend([nome_col1, nome_col2])
                # Remove a coluna original após extração
                df = df.drop(columns=[col])
            else:
                novas_colunas.append(col)
        
        # Reordena o DataFrame mantendo a ordem original (com as inserções)
        df = df[novas_colunas]
        
        # 2. Ações Repetitivas (Sem remoção de duplicatas)
        df = df.dropna(how='all')  # Remove apenas linhas onde TUDO é nulo
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')] # Limpa colunas vazias à direita
        
        # 3. Padronização Profissional de Colunas
        # Remove espaços, coloca em minúsculo e tira acentos básicos (opcional)
        df.columns = [
            str(c).strip().lower().replace(" ", "_").replace(".", "_") 
            for c in df.columns
        ]
        
        # 4. Resumo para o Agente de IA
        return {
            "status": "sucesso",
            "formato": extensao,
            "total_linhas": len(df),
            "colunas_padronizadas": list(df.columns),
            "amostra": df.head(5).to_dict(orient='records')
        }

    except Exception as e:
        return {"status": "erro", "mensagem": f"Falha ao processar {caminho}: {str(e)}"}
