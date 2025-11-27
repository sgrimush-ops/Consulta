#!/bin/bash
# Script de início rápido para corrigir o erro da tabela ofertas

set -e  # Para na primeira falha

echo "=========================================="
echo "CORREÇÃO RÁPIDA - Tabela Ofertas"
echo "=========================================="
echo ""

# Verifica se DATABASE_URL está definida
if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "❌ ERRO: DATABASE_URL não está definida!"
    echo ""
    echo "Para corrigir, execute um dos comandos abaixo:"
    echo ""
    echo "1. Definir temporariamente (apenas para esta sessão):"
    echo "   export DATABASE_URL='postgresql://user:password@host:port/database'"
    echo ""
    echo "2. Se estiver no Render ou similar, a variável deve estar disponível"
    echo "   Verifique as configurações do seu ambiente."
    echo ""
    exit 1
fi

echo "✓ DATABASE_URL encontrada"
echo ""

# Verifica se Python está disponível
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "❌ ERRO: Python não encontrado!"
    echo "Instale Python 3.x para continuar."
    exit 1
fi

# Define o comando Python correto
PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    PYTHON_CMD="python"
fi

echo "✓ Python encontrado: $PYTHON_CMD"
echo ""

# Verifica se SQLAlchemy está instalada
echo "Verificando dependências..."
if ! $PYTHON_CMD -c "import sqlalchemy" 2>/dev/null; then
    echo "⚠ SQLAlchemy não encontrada. Instalando..."
    pip install sqlalchemy psycopg2-binary
fi

echo "✓ Dependências OK"
echo ""

# Executa o script de diagnóstico
echo "Executando diagnóstico e correção..."
echo "=========================================="
echo ""

$PYTHON_CMD diagnose_ofertas.py

echo ""
echo "=========================================="
echo "Processo concluído!"
echo "=========================================="
