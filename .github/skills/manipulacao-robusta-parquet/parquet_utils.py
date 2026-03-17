#!/usr/bin/env python3
"""
Utilidades para Manipulação de Arquivos Parquet

Fornece funções prontas para validação, diagnóstico e conversão de parquets.
Uso por agentes: importar funções ou usar como CLI.

Exemplos CLI:
    python parquet_utils.py info bdados/con5cod.parquet
    python parquet_utils.py validate bdados/consumo.parquet
    python parquet_utils.py sample bdados/con5cod.parquet 10
    python parquet_utils.py csv-to-parquet dados.csv dados.parquet
"""

import sys
import os
import pandas as pd
import pyarrow.parquet as pq
from pathlib import Path
from typing import Tuple, Dict, Any


class ParquetUtils:
    """Utilidades para trabalhar com arquivos Parquet."""
    
    @staticmethod
    def info(arquivo: str) -> Dict[str, Any]:
        """
        Retorna metadados do arquivo parquet.
        
        Returns:
            dict: {
                'num_rows': int,
                'num_columns': int,
                'colunas': list,
                'tipos': dict,
                'tamanho_mb': float
            }
        """
        try:
            # Ler arquivo para obter informações
            df = pd.read_parquet(arquivo)
            
            # Tamanho do arquivo físico
            tamanho_mb = os.path.getsize(arquivo) / (1024 ** 2)
            
            info_dict = {
                'num_rows': len(df),
                'num_columns': len(df.columns),
                'colunas': list(df.columns),
                'tipos': {col: str(df[col].dtype) for col in df.columns},
                'tamanho_mb_comprimido': round(tamanho_mb, 2),
                'tamanho_mb_descomprimido': round(df.memory_usage(deep=True).sum() / (1024 ** 2), 2)
            }
            return info_dict
        except Exception as e:
            raise Exception(f"Erro ao ler metadados: {e}")
    
    @staticmethod
    def validate(arquivo: str, verbose: bool = True) -> Tuple[bool, str]:
        """
        Valida integridade de arquivo parquet.
        
        Returns:
            (bool: válido, str: mensagem)
        """
        issues = []
        
        try:
            # 1. Arquivo existe?
            if not os.path.exists(arquivo):
                return False, f"❌ Arquivo não encontrado: {arquivo}"
            
            # 2. Consegue ler?
            df = pd.read_parquet(arquivo)
            
            # 3. Validações básicas
            if df.shape[0] == 0:
                issues.append("⚠️  Arquivo está vazio (0 linhas)")
            
            if df.shape[1] == 0:
                return False, "❌ Nenhuma coluna no arquivo"
            
            # 4. Detectar problemas
            n_duplicados = df.duplicated().sum()
            if n_duplicados > 0:
                issues.append(f"⚠️  {n_duplicados} linhas completas duplicadas")
            
            # 5. Nulos por coluna
            for col in df.columns:
                n_nulos = df[col].isna().sum()
                taxa = (n_nulos / len(df)) * 100
                if n_nulos > 0:
                    issues.append(f"⚠️  {col}: {n_nulos} nulos ({taxa:.1f}%)")
            
            # 6. Tipos de dados
            pf = pq.ParquetFile(arquivo)
            schema = pf.schema
            
            # 7. Resultado
            if issues:
                msg = f"✅ Parquet lido ({df.shape[0]} linhas, {df.shape[1]} colunas)\n"
                msg += "Avisos encontrados:\n" + "\n".join(issues)
                return True, msg
            else:
                msg = f"✅ Parquet válido: {df.shape[0]} linhas, {df.shape[1]} colunas"
                return True, msg
        
        except Exception as e:
            return False, f"❌ Erro ao validar: {e}"
    
    @staticmethod
    def sample(arquivo: str, n_rows: int = 5) -> pd.DataFrame:
        """
        Retorna amostra das primeiras N linhas.
        
        Args:
            arquivo: caminho do parquet
            n_rows: número de linhas a amostrar
        
        Returns:
            DataFrame com amostra
        """
        return pd.read_parquet(arquivo).head(n_rows)
    
    @staticmethod
    def columns_info(arquivo: str) -> Dict[str, Dict]:
        """
        Retorna informações detalhadas sobre cada coluna.
        
        Returns:
            {
                'column_name': {
                    'tipo': 'int64',
                    'nulos': 10,
                    'min': 1,
                    'max': 9999,
                    'unicos': 8500
                }
            }
        """
        df = pd.read_parquet(arquivo)
        pf = pq.ParquetFile(arquivo)
        schema = pf.schema
        
        info = {}
        for col in df.columns:
            col_info = {
                'tipo': str(schema.field(col).type),
                'nulos': int(df[col].isna().sum()),
                'unicos': int(df[col].nunique())
            }
            
            # Estatísticas numéricas se possível
            if pd.api.types.is_numeric_dtype(df[col]):
                col_info.update({
                    'min': float(df[col].min()) if not df[col].empty else None,
                    'max': float(df[col].max()) if not df[col].empty else None,
                    'media': float(df[col].mean()) if not df[col].empty else None,
                })
            
            info[col] = col_info
        
        return info
    
    @staticmethod
    def csv_to_parquet(
        csv_file: str,
        output_parquet: str,
        sep: str = ';',
        encoding: str = 'utf-8',
        compression: str = 'snappy',
        **kwargs
    ) -> Tuple[bool, str]:
        """
        Converte CSV para Parquet com validações.
        
        Args:
            csv_file: arquivo CSV de entrada
            output_parquet: arquivo Parquet de saída
            sep: separador (default ';')
            encoding: encoding (default 'utf-8')
            compression: 'snappy', 'gzip', 'brotli', None
        
        Returns:
            (bool: sucesso, str: mensagem)
        """
        try:
            # 1. Carregar CSV
            df = pd.read_csv(
                csv_file,
                sep=sep,
                encoding=encoding,
                **kwargs
            )
            
            # 2. Validar
            if df.shape[0] == 0:
                return False, f"❌ CSV está vazio"
            
            # 3. Exportar
            df.to_parquet(
                output_parquet,
                engine='pyarrow',
                compression=compression,
                index=False
            )
            
            # 4. Verificar resultado
            pf = pq.ParquetFile(output_parquet)
            tamanho_csv = os.path.getsize(csv_file) / (1024 ** 2)
            tamanho_parquet = pf.metadata.size / (1024 ** 2)
            reducao = ((tamanho_csv - tamanho_parquet) / tamanho_csv) * 100
            
            msg = f"✅ Convertido: {df.shape[0]} linhas, {df.shape[1]} colunas\n"
            msg += f"   CSV: {tamanho_csv:.2f} MB → Parquet: {tamanho_parquet:.2f} MB (-{reducao:.1f}%)"
            
            return True, msg
        
        except Exception as e:
            return False, f"❌ Erro na conversão: {e}"
    
    @staticmethod
    def parquet_to_csv(
        parquet_file: str,
        output_csv: str,
        sep: str = ';',
        encoding: str = 'utf-8'
    ) -> Tuple[bool, str]:
        """
        Converte Parquet para CSV.
        
        Args:
            parquet_file: arquivo Parquet de entrada
            output_csv: arquivo CSV de saída
            sep: separador (default ';')
            encoding: encoding (default 'utf-8')
        
        Returns:
            (bool: sucesso, str: mensagem)
        """
        try:
            df = pd.read_parquet(parquet_file)
            df.to_csv(
                output_csv,
                sep=sep,
                encoding=encoding,
                index=False
            )
            
            tamanho_parquet = os.path.getsize(parquet_file) / (1024 ** 2)
            tamanho_csv = os.path.getsize(output_csv) / (1024 ** 2)
            aumento = ((tamanho_csv - tamanho_parquet) / tamanho_parquet) * 100
            
            msg = f"✅ Convertido: {df.shape[0]} linhas para CSV\n"
            msg += f"   Parquet: {tamanho_parquet:.2f} MB → CSV: {tamanho_csv:.2f} MB (+{aumento:.1f}%)"
            
            return True, msg
        
        except Exception as e:
            return False, f"❌ Erro na conversão: {e}"
    
    @staticmethod
    def merge_parquets(
        lista_arquivos: list,
        output_parquet: str,
        compression: str = 'snappy'
    ) -> Tuple[bool, str]:
        """
        Mescla múltiplos parquets em um.
        
        Args:
            lista_arquivos: lista de caminhos parquet
            output_parquet: arquivo de saída
            compression: tipo de compressão
        
        Returns:
            (bool: sucesso, str: mensagem)
        """
        try:
            dfs = [
                pd.read_parquet(arquivo)
                for arquivo in lista_arquivos
            ]
            
            df_merged = pd.concat(dfs, ignore_index=True)
            
            df_merged.to_parquet(
                output_parquet,
                engine='pyarrow',
                compression=compression,
                index=False
            )
            
            msg = f"✅ Mesclados {len(lista_arquivos)} parquets\n"
            msg += f"   Total: {df_merged.shape[0]} linhas, {df_merged.shape[1]} colunas"
            
            return True, msg
        
        except Exception as e:
            return False, f"❌ Erro na mesclagem: {e}"


def main():
    """CLI para utilidades de parquet."""
    
    if len(sys.argv) < 2:
        print("Uso: python parquet_utils.py <comando> <args>")
        print("\nComandos:")
        print("  info <arquivo>               - Metadados do parquet")
        print("  validate <arquivo>           - Valida integridade")
        print("  columns <arquivo>            - Info detalhada de colunas")
        print("  sample <arquivo> [n]         - Mostra primeiras N linhas")
        print("  csv-to-parquet <csv> <out>   - Converte CSV → Parquet")
        print("  parquet-to-csv <par> <csv>   - Converte Parquet → CSV")
        print("  merge <out> <arquivo1> ...   - Mescla múltiplos parquets")
        sys.exit(1)
    
    comando = sys.argv[1]
    
    try:
        if comando == 'info':
            arquivo = sys.argv[2]
            info = ParquetUtils.info(arquivo)
            print(f"\n📊 Info: {arquivo}")
            for key, value in info.items():
                if key == 'tipos':
                    print(f"  Tipos de dados:")
                    for col, tipo in value.items():
                        print(f"    {col}: {tipo}")
                elif key == 'colunas':
                    print(f"  Colunas ({len(value)}): {', '.join(value)}")
                else:
                    print(f"  {key}: {value}")
        
        elif comando == 'validate':
            arquivo = sys.argv[2]
            ok, msg = ParquetUtils.validate(arquivo)
            print(f"\n{msg}")
            sys.exit(0 if ok else 1)
        
        elif comando == 'columns':
            arquivo = sys.argv[2]
            cols = ParquetUtils.columns_info(arquivo)
            print(f"\n📋 Colunas: {arquivo}\n")
            for col, info in cols.items():
                print(f"  {col}:")
                for key, val in info.items():
                    if isinstance(val, float):
                        print(f"    {key}: {val:.2f}")
                    else:
                        print(f"    {key}: {val}")
        
        elif comando == 'sample':
            arquivo = sys.argv[2]
            n = int(sys.argv[3]) if len(sys.argv) > 3 else 5
            df = ParquetUtils.sample(arquivo, n)
            print(f"\n📄 Amostra: {arquivo} (primeiras {n} linhas)\n")
            print(df.to_string())
        
        elif comando == 'csv-to-parquet':
            csv_file = sys.argv[2]
            output = sys.argv[3]
            ok, msg = ParquetUtils.csv_to_parquet(csv_file, output)
            print(f"\n{msg}")
            sys.exit(0 if ok else 1)
        
        elif comando == 'parquet-to-csv':
            parquet_file = sys.argv[2]
            output = sys.argv[3]
            ok, msg = ParquetUtils.parquet_to_csv(parquet_file, output)
            print(f"\n{msg}")
            sys.exit(0 if ok else 1)
        
        elif comando == 'merge':
            output = sys.argv[2]
            arquivos = sys.argv[3:]
            ok, msg = ParquetUtils.merge_parquets(arquivos, output)
            print(f"\n{msg}")
            sys.exit(0 if ok else 1)
        
        else:
            print(f"❌ Comando desconhecido: {comando}")
            sys.exit(1)
    
    except IndexError:
        print("❌ Argumentos insuficientes")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Erro: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
