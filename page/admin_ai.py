from __future__ import annotations

import csv
from pathlib import Path

import streamlit as st


ROOT_DIR = Path(__file__).resolve().parent.parent
GITHUB_DIR = ROOT_DIR / ".github"
AGENTS_DIR = GITHUB_DIR / "agents"
SKILLS_DIR = GITHUB_DIR / "skills"
PROMPTS_DIR = GITHUB_DIR / "prompts"
SQUAD_DIR = ROOT_DIR / "squads" / "varejo-insight"
DOCS_PATH = ROOT_DIR / "doc" / "AGENTES_SQUADS_SKILLS.md"
SQUAD_FILE = SQUAD_DIR / "squad.yaml"
SQUAD_PARTY_FILE = SQUAD_DIR / "squad-party.csv"
PIPELINE_FILE = SQUAD_DIR / "pipeline" / "pipeline.yaml"
PROMPT_FILE = PROMPTS_DIR / "executar-squad-varejo-insight.prompt.md"


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _parse_frontmatter(path: Path) -> dict:
    content = _read_text(path)
    if not content.startswith("---"):
        return {}

    lines = content.splitlines()
    data = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"')
    return data


def _parse_simple_yaml(path: Path) -> dict:
    content = _read_text(path)
    data = {}
    current_list = None

    for raw_line in content.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()

        if indent == 0 and line.endswith(":"):
            current_list = line[:-1]
            data[current_list] = []
            continue

        if indent == 0 and ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip().strip('"')
            current_list = None
            continue

        if current_list and line.startswith("- "):
            data[current_list].append(line[2:].strip().strip('"'))

    return data


def _markdown_summary(path: Path, max_chars: int = 240) -> str:
    content = _read_text(path)
    if not content:
        return ""

    lines = []
    in_frontmatter = content.startswith("---")
    for line in content.splitlines():
        stripped = line.strip()
        if in_frontmatter:
            if stripped == "---":
                in_frontmatter = False
            continue
        if not stripped or stripped.startswith("#") or stripped.startswith("---"):
            continue
        lines.append(stripped)
        if len(" ".join(lines)) >= max_chars:
            break

    summary = " ".join(lines).strip()
    if len(summary) > max_chars:
        summary = summary[: max_chars - 3].rstrip() + "..."
    return summary


def _load_agents() -> list[dict]:
    items = []
    for path in sorted(AGENTS_DIR.glob("*.agent.md")):
        frontmatter = _parse_frontmatter(path)
        items.append(
            {
                "nome": frontmatter.get("name", path.stem),
                "descricao": frontmatter.get("description", ""),
                "resumo": _markdown_summary(path),
                "arquivo": path,
            }
        )
    return items


def _load_skills() -> list[dict]:
    items = []
    for path in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        frontmatter = _parse_frontmatter(path)
        items.append(
            {
                "nome": frontmatter.get("name", path.parent.name),
                "descricao": frontmatter.get("description", ""),
                "resumo": _markdown_summary(path),
                "arquivo": path,
                "script": next(path.parent.glob("scripts/*.py"), None),
            }
        )
    return items


def _load_prompts() -> list[dict]:
    items = []
    for path in sorted(PROMPTS_DIR.glob("*.prompt.md")):
        frontmatter = _parse_frontmatter(path)
        items.append(
            {
                "nome": frontmatter.get("name", path.stem),
                "descricao": frontmatter.get("description", ""),
                "agent": frontmatter.get("agent", ""),
                "resumo": _markdown_summary(path),
                "arquivo": path,
            }
        )
    return items


def _load_squad_party() -> list[dict]:
    if not SQUAD_PARTY_FILE.exists():
        return []

    with SQUAD_PARTY_FILE.open("r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        return list(reader)


def _load_pipeline_definition() -> dict:
    content = _read_text(PIPELINE_FILE)
    pipeline = {"name": "", "entrypoint": "", "steps": []}
    current_id = None

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if line.startswith("name:"):
            pipeline["name"] = line.split(":", 1)[1].strip()
        elif line.startswith("entrypoint:"):
            pipeline["entrypoint"] = line.split(":", 1)[1].strip()
        elif line.startswith("- id:"):
            current_id = line.split(":", 1)[1].strip()
        elif line.startswith("file:") and current_id:
            pipeline["steps"].append(
                {
                    "id": current_id,
                    "file": line.split(":", 1)[1].strip(),
                }
            )
            current_id = None

    return pipeline


def _validate_integration() -> list[dict]:
    results = []
    squad_cfg = _parse_simple_yaml(SQUAD_FILE)
    pipeline_cfg = _load_pipeline_definition()
    squad_party = _load_squad_party()

    def add(level: str, message: str) -> None:
        results.append({"level": level, "message": message})

    required_files = [
        ("Instrucoes globais", GITHUB_DIR / "copilot-instructions.md"),
        ("Squad principal", SQUAD_FILE),
        ("Party do squad", SQUAD_PARTY_FILE),
        ("Pipeline do squad", PIPELINE_FILE),
        ("Guia operacional", DOCS_PATH),
        ("Prompt do squad", PROMPT_FILE),
    ]
    for label, path in required_files:
        if path.exists():
            add("ok", f"{label} presente: {path.relative_to(ROOT_DIR)}")
        else:
            add("error", f"{label} ausente: {path.relative_to(ROOT_DIR)}")

    for skill_name in squad_cfg.get("skills", []):
        skill_path = SKILLS_DIR / skill_name / "SKILL.md"
        if skill_path.exists():
            add("ok", f"Skill do squad encontrada: {skill_name}")
        else:
            add("error", f"Skill referenciada no squad nao encontrada em .github/skills: {skill_name}")

    for data_path in squad_cfg.get("data", []):
        full_path = SQUAD_DIR / data_path
        if full_path.exists():
            add("ok", f"Arquivo de dados do squad encontrado: {data_path}")
        else:
            add("error", f"Arquivo de dados do squad ausente: {data_path}")

    for row in squad_party:
        relative_party_path = row.get("path", "")
        cleaned_party_path = relative_party_path[2:] if relative_party_path.startswith("./") else relative_party_path
        party_file = SQUAD_DIR / cleaned_party_path
        if party_file.exists():
            add("ok", f"Agente da party encontrado: {cleaned_party_path}")
        else:
            add("error", f"Agente listado na party nao encontrado: {cleaned_party_path}")

        github_agent = AGENTS_DIR / party_file.name
        if github_agent.exists():
            add("ok", f"Agente da party espelhado em .github/agents: {github_agent.name}")
        else:
            add("warning", f"Agente da party sem equivalente em .github/agents: {party_file.name}")

    entrypoint = pipeline_cfg.get("entrypoint")
    if entrypoint:
        entrypoint_path = SQUAD_DIR / "pipeline" / entrypoint
        if entrypoint_path.exists():
            add("ok", f"Entrypoint do pipeline encontrado: {entrypoint}")
        else:
            add("error", f"Entrypoint do pipeline ausente: {entrypoint}")

    for step in pipeline_cfg.get("steps", []):
        step_file = SQUAD_DIR / "pipeline" / step["file"]
        if step_file.exists():
            add("ok", f"Step do pipeline encontrado: {step['id']} -> {step['file']}")
        else:
            add("error", f"Step do pipeline ausente: {step['id']} -> {step['file']}")

    if not squad_party:
        add("warning", "A party do squad esta vazia.")
    if not pipeline_cfg.get("steps"):
        add("warning", "O pipeline nao possui steps cadastrados.")

    return results


def _render_collection(title: str, items: list[dict], kind: str) -> None:
    st.subheader(title)
    if not items:
        st.warning(f"Nenhum {kind} encontrado.")
        return

    for item in items:
        with st.expander(item["nome"], expanded=False):
            if item.get("descricao"):
                st.write(item["descricao"])
            if item.get("resumo"):
                st.caption(item["resumo"])
            if item.get("agent"):
                st.caption(f"Agente associado: {item['agent']}")
            if item.get("script"):
                st.caption(f"Script: {item['script'].relative_to(ROOT_DIR)}")
            st.caption(f"Arquivo: {item['arquivo'].relative_to(ROOT_DIR)}")
            st.download_button(
                label="Baixar conteudo",
                data=_read_text(item["arquivo"]),
                file_name=item["arquivo"].name,
                mime="text/plain",
                key=f"download-{kind}-{item['arquivo'].name}",
            )


def _render_reference_explorer(agents: list[dict], skills: list[dict], prompts: list[dict]) -> None:
    st.subheader("Explorador de Referencias")
    references = {
        "Guia operacional": DOCS_PATH,
        "Squad principal": SQUAD_FILE,
        "Party do squad": SQUAD_PARTY_FILE,
        "Pipeline do squad": PIPELINE_FILE,
        "Prompt do squad": PROMPT_FILE,
    }

    for item in agents:
        references[f"Agente: {item['nome']}"] = item["arquivo"]
    for item in skills:
        references[f"Skill: {item['nome']}"] = item["arquivo"]
    for item in prompts:
        references[f"Prompt: {item['nome']}"] = item["arquivo"]

    selected_label = st.selectbox("Escolha um artefato para visualizar", list(references.keys()))
    selected_path = references[selected_label]
    preview_lines = st.slider("Linhas para visualizar", min_value=20, max_value=200, value=60, step=20)
    content = _read_text(selected_path)

    st.caption(f"Arquivo: {selected_path.relative_to(ROOT_DIR)}")
    if content:
        preview = "\n".join(content.splitlines()[:preview_lines])
        language = "yaml" if selected_path.suffix in {".yaml", ".yml"} else "markdown"
        st.code(preview, language=language)
        st.download_button(
            label="Baixar arquivo selecionado",
            data=content,
            file_name=selected_path.name,
            mime="text/plain",
            key=f"download-reference-{selected_path.name}",
        )
    else:
        st.warning("Nao foi possivel ler o conteudo do arquivo selecionado.")


def _render_validation_report() -> None:
    st.subheader("Validacao Automatica")
    results = _validate_integration()

    total_ok = sum(1 for item in results if item["level"] == "ok")
    total_warning = sum(1 for item in results if item["level"] == "warning")
    total_error = sum(1 for item in results if item["level"] == "error")

    col1, col2, col3 = st.columns(3)
    col1.metric("Checks OK", total_ok)
    col2.metric("Warnings", total_warning)
    col3.metric("Erros", total_error)

    if total_error == 0 and total_warning == 0:
        st.success("Nenhuma inconsistencia encontrada entre squad, party e pipeline.")
    elif total_error == 0:
        st.warning("Validacao concluida com avisos, mas sem erros bloqueantes.")
    else:
        st.error("Validacao encontrou inconsistencias que merecem correcao.")

    for item in results:
        if item["level"] == "ok":
            st.caption(f"OK: {item['message']}")
        elif item["level"] == "warning":
            st.warning(item["message"])
        else:
            st.error(item["message"])


def show_admin_ai_page(engine=None, base_data_path=None):
    if st.session_state.get("role") != "admin":
        st.error("Acesso restrito a administradores.")
        st.stop()

    st.title("Integracao de IA")
    st.caption("Painel administrativo para agentes, squads e skills integrados ao ProjetoBak.")

    agents = _load_agents()
    skills = _load_skills()
    prompts = _load_prompts()
    squad_party = _load_squad_party()
    pipeline = _load_pipeline_definition()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Agentes", len(agents))
    col2.metric("Skills", len(skills))
    col3.metric("Prompts", len(prompts))
    col4.metric("Etapas do Squad", len(pipeline.get("steps", [])))

    st.markdown("---")
    st.subheader("Resumo Operacional")
    st.write(f"Squad ativo: {pipeline.get('name') or 'Varejo Insight'}")
    st.write(f"Agentes definidos na party: {len(squad_party)}")
    st.write(f"Entrypoint do pipeline: {pipeline.get('entrypoint', 'nao definido')}")

    referenced_skills = _parse_simple_yaml(SQUAD_FILE).get("skills", [])
    if referenced_skills:
        st.write("Skills referenciadas no squad: " + ", ".join(referenced_skills))

    st.markdown("---")
    _render_reference_explorer(agents, skills, prompts)

    st.markdown("---")
    _render_validation_report()

    st.markdown("---")
    st.subheader("Squad Varejo Insight")
    st.caption("Fonte canonica usada pela integracao de IA no projeto.")
    for step in pipeline.get("steps", []):
        st.write(f"{step['id']} -> {step['file']}")

    st.markdown("---")
    _render_collection("Agentes Disponiveis", agents, "agente")
    st.markdown("---")
    _render_collection("Skills Disponiveis", skills, "skill")
    st.markdown("---")
    _render_collection("Prompts Disponiveis", prompts, "prompt")

    st.markdown("---")
    st.subheader("Como usar")
    st.info(
        "No VS Code/Copilot, use o prompt 'Executar Squad Varejo Insight' "
        "ou selecione um dos agentes especializados em .github/agents/."
    )