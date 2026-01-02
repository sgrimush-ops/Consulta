"""
Script de teste para verificar se o scanner de código de barras está funcionando.
Execute este script depois de instalar as dependências.
"""

try:
    from pyzbar.pyzbar import decode
    from PIL import Image
    print("✅ Todas as dependências estão instaladas corretamente!")
    print("   - pyzbar: OK")
    print("   - PIL (Pillow): OK")
    print("\nO scanner de código de barras está pronto para uso! 📷")
except ImportError as e:
    print(f"❌ Erro ao importar dependências: {e}")
    print("\nPor favor, instale as dependências com:")
    print("   pip install -r requirements.txt")
