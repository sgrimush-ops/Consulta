# Pacote de Implantação de Agentes, Squads e Skills

Esta pasta contém o backup e a consolidação das inteligências desenvolvidas localmente. O objetivo deste pacote é facilitar o *upload* e a integração no seu novo ecossistema na nuvem (GitHub/Server).

## Estrutura da Pasta

- **`agentes/`**: Contém todos os perfis YAML/Markdown de agentes individuais (ex: `anton-engenheiro-software.agent.md`, `danilo-dados.agent.md`, etc).
- **`squads/`**: Contém as definições e configurações dos times de agentes (Squads), juntamente com os fluxos e orquestrações se existirem.
- **`skills/`**: Contém todas as ferramentas e capacidades que os agentes podem utilizar (ex: `carregar_e_sanitizar`, etc.), incluindo seus respectivos `SKILL.md`.

## Instruções para a IA da Nuvem

Quando você subir estes arquivos para seu projeto (via GitHub ou upload direto), instrua a IA residente com o seguinte prompt base:

> *"Olá, estou migrando minha estrutura local de inteligência de agentes para cá. Nas pastas `agentes`, `squads` e `skills` estão as definições em Markdown/YAML que usávamos. Por favor, leia os arquivos, entenda o propósito de cada agente, grupo e ferramenta, e adapte os caminhos/arquitetura para o padrão exigido por este novo projeto na nuvem. Mantenha os Prompts (Personas e Principles) intactos."*

---

> **Aviso:** Esta pasta `tmp/implantacao` é estritamente temporária. Após ter certeza que os arquivos subiram no Github/Nuvem de forma íntegra, você pode excluir essa pasta inteira do seu computador local.
