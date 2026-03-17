#!/usr/bin/env python3
"""
Validator: Adicionar Página Autenticada

Valida se uma nova página foi adicionada corretamente seguindo o padrão
do ProjetoBak (import em app.py, rota no dicionário pages, etc).

Uso:
    python .github/skills/adicionar-pagina-autenticada/validar_pagina.py nome_pagina
    python .github/skills/adicionar-pagina-autenticada/validar_pagina.py relatorio_vendas
"""

import sys
import os
import re
import ast
from pathlib import Path

def find_project_root():
    """Encontra /workspaces/ProjetoBak"""
    current = Path(__file__).resolve()
    while current != current.parent:
        if (current / "app.py").exists() and (current / "page").exists():
            return current
        current = current.parent
    return Path("/workspaces/ProjetoBak")

PROJECT_ROOT = find_project_root()

def check_page_file_exists(page_name):
    """✓ Arquivo page/NOME.py deve existir"""
    page_file = PROJECT_ROOT / "page" / f"{page_name}.py"
    if not page_file.exists():
        return False, f"Arquivo não encontrado: {page_file}"
    return True, f"✓ Arquivo existe: {page_file.relative_to(PROJECT_ROOT)}"

def check_function_defined(page_name):
    """✓ Função show_NOME_page() deve ser definida"""
    page_file = PROJECT_ROOT / "page" / f"{page_name}.py"
    function_name = f"show_{page_name}_page"
    
    try:
        with open(page_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if function is defined
        pattern = rf"def {function_name}\s*\("
        if not re.search(pattern, content):
            return False, f"Função '{function_name}()' não definida em {page_file.name}"
        
        # Check if function accepts engine and base_data_path
        pattern = rf"def {function_name}\s*\([^)]*engine[^)]*base_data_path[^)]*\)"
        if not re.search(pattern, content):
            return False, f"Função deve aceitar 'engine' e 'base_data_path'"
        
        return True, f"✓ Função {function_name}(engine, base_data_path) definida"
    except Exception as e:
        return False, f"Erro ao analisar {page_file.name}: {e}"

def check_import_in_app(page_name):
    """✓ Página deve ser importada em app.py"""
    app_file = PROJECT_ROOT / "app.py"
    function_name = f"show_{page_name}_page"
    
    try:
        with open(app_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check import statement
        patterns = [
            rf"from page\.{page_name} import {function_name}",
            rf"from page\.{page_name} import.*{function_name}",
        ]
        
        if not any(re.search(p, content) for p in patterns):
            return False, f"Import não encontrado em app.py: from page.{page_name} import {function_name}"
        
        return True, f"✓ Importação em app.py: from page.{page_name} import {function_name}"
    except Exception as e:
        return False, f"Erro ao verificar app.py: {e}"

def check_route_in_pages_dict(page_name):
    """✓ Página deve estar no dicionário 'pages' em app.py"""
    app_file = PROJECT_ROOT / "app.py"
    function_name = f"show_{page_name}_page"
    
    try:
        with open(app_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Look for: "Label": lambda: show_NOME_page(engine, BASE_DATA_PATH)
        pattern = rf'pages\s*=\s*\{{[^}}]*{function_name}\s*\([^)]*engine[^)]*BASE_DATA_PATH[^)]*\)[^}}]*\}}'
        
        # More lenient check: just look for the function call in pages dict
        if f'{function_name}(' not in content or 'pages' not in content:
            return False, f"Função '{function_name}' não referenciada em 'pages' dict em app.py"
        
        # Try to find the specific line
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if f"{function_name}(" in line and i > 0:
                # Found it, check if lambda
                context = '\n'.join(lines[max(0, i-2):min(len(lines), i+3)])
                if 'pages' in context or 'lambda' in context:
                    return True, f"✓ Rota encontrada em 'pages' dict"
        
        return False, f"Função não encontrada em 'pages' dict"
    except Exception as e:
        return False, f"Erro ao verificar pages dict: {e}"

def check_role_validation(page_name):
    """✓ Página deve validar role/lojas_acesso"""
    page_file = PROJECT_ROOT / "page" / f"{page_name}.py"
    
    try:
        with open(page_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        checks = [
            ('role' in content, "validação de 'role'"),
            ('st.session_state' in content, "uso de 'st.session_state'"),
            ('st.error' in content, "mensagem de erro (st.error)"),
        ]
        
        missing = [name for check, name in checks if not check]
        if missing:
            return False, f"Faltam validações de segurança: {', '.join(missing)}"
        
        return True, f"✓ Validações de segurança (role/session_state/erro) presentes"
    except Exception as e:
        return False, f"Erro ao validar segurança: {e}"

def validate_page(page_name):
    """Executa todas as validações"""
    print(f"\n🔍 Validando página: {page_name}")
    print("=" * 60)
    
    validators = [
        ("Arquivo existe", check_page_file_exists),
        ("Função definida", check_function_defined),
        ("Importação em app.py", check_import_in_app),
        ("Rota em 'pages' dict", check_route_in_pages_dict),
        ("Validação de segurança", check_role_validation),
    ]
    
    results = []
    for label, validator in validators:
        ok, message = validator(page_name)
        status = "✅" if ok else "❌"
        print(f"{status} {label}: {message}")
        results.append((label, ok))
    
    print("=" * 60)
    total = len(results)
    passed = sum(1 for _, ok in results if ok)
    
    if passed == total:
        print(f"\n✅ VALIDAÇÃO PASSOU: {passed}/{total} checks")
        return 0
    else:
        print(f"\n❌ VALIDAÇÃO FALHOU: {passed}/{total} checks")
        return 1

def main():
    if len(sys.argv) < 2:
        print("Uso: python validar_pagina.py <nome_pagina>")
        print("Ex:  python validar_pagina.py relatorio_vendas")
        sys.exit(1)
    
    page_name = sys.argv[1].strip()
    exit_code = validate_page(page_name)
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
