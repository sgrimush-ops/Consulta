#!/bin/bash
# Script para commit e push automático do submódulo ProjetoBak_Sincronizador
# Uso: ./sub_commit.sh "mensagem do commit"

if [ -z "$1" ]; then
  echo "Uso: $0 'mensagem do commit'"
  exit 1
fi

# Commita e faz push no submódulo
cd "$(dirname "$0")"
git add .
git commit -m "$1"
git push

# Volta para a raiz do projeto e atualiza o submódulo no repositório principal
cd ..
git add ProjetoBak_Sincronizador
git commit -m "chore(submodule): atualiza ProjetoBak_Sincronizador após ajuste"
git push
