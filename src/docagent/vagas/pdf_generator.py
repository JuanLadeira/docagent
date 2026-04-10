"""
Gerador de PDF de currículo adaptado para candidaturas.

Usa PyMuPDF (fitz) — já instalado via pymupdf.
Retorna bytes do PDF gerado em memória.

O PDF é um currículo completo adaptado para a vaga específica:
  • Header: nome, cargo da vaga, contato
  • Objetivo Profissional: resumo_personalizado (LLM, adaptado para esta vaga)
  • Competências: skills do Candidato
  • Experiência Profissional: estruturada do Candidato (original)
  • Formação Acadêmica: estruturada do Candidato (original)
  • Seções extras detectadas no cv_texto (Idiomas, Certificações, Projetos, etc.)

A carta de apresentação NÃO é incluída no PDF — fica disponível só na tela.
"""
import re
import textwrap
from dataclasses import dataclass, field


@dataclass
class DadosCandidatura:
    nome_candidato: str
    email: str
    telefone: str
    cargo_desejado: str       # cargo do Candidato
    titulo_vaga: str          # título da Vaga (usado no header)
    empresa: str
    resumo_personalizado: str  # objetivo adaptado para esta vaga (LLM)
    skills: list               # list[str]
    experiencias: list         # list[dict] com cargo/empresa/periodo/descricao
    formacao: list             # list[dict] com grau/curso/instituicao/ano
    cv_texto: str = ""         # texto bruto extraído do PDF original
    simplificada: bool = False


# ── Detecção de seções extras no cv_texto ────────────────────────────────────

# Seções que já são tratadas de forma estruturada — ignorar no cv_texto
_SECOES_IGNORADAS = {
    "experiência", "experiencias", "experiência profissional",
    "formação", "formacao", "formação acadêmica", "educação", "educacao",
    "habilidades", "competências", "competencias", "skills", "tecnologias",
    "objetivo", "resumo", "perfil", "sobre mim", "summary", "objective",
    "dados pessoais", "informações pessoais", "contato",
}

# Seções extras que queremos capturar
_SECOES_EXTRAS_CONHECIDAS = {
    "idiomas", "languages", "línguas",
    "certificações", "certificacoes", "certifications", "certificados",
    "projetos", "projects",
    "cursos", "treinamentos", "trainings",
    "prêmios", "premios", "awards",
    "publicações", "publicacoes", "publications",
    "voluntariado", "volunteer",
    "associações", "memberships",
    "referências", "references",
}


def _detectar_secoes_extras(cv_texto: str) -> list[tuple[str, str]]:
    """
    Varre cv_texto e retorna seções extras não cobertas pelos campos estruturados.
    Retorna lista de (titulo_secao, conteudo).
    """
    if not cv_texto or not cv_texto.strip():
        return []

    linhas = cv_texto.splitlines()
    secoes: list[tuple[str, str]] = []
    secao_atual: str | None = None
    conteudo_atual: list[str] = []

    def _e_titulo_secao(linha: str) -> str | None:
        """Retorna o título normalizado se a linha parecer um cabeçalho de seção, senão None."""
        s = linha.strip()
        if not s or len(s) > 60:
            return None
        # Cabeçalho: linha em caixa alta, ou linha curta seguida de --- ou ===
        normalizado = s.lower().rstrip(":_- ")
        if normalizado in _SECOES_EXTRAS_CONHECIDAS:
            return s.rstrip(":_ ")
        # Linha toda maiúscula curta (ex: "IDIOMAS", "CERTIFICAÇÕES")
        if s.isupper() and 3 < len(s) < 50:
            if normalizado not in _SECOES_IGNORADAS:
                return s.title()
        return None

    for linha in linhas:
        titulo = _e_titulo_secao(linha)
        if titulo:
            # Fecha seção anterior
            if secao_atual and conteudo_atual:
                conteudo = "\n".join(l for l in conteudo_atual if l.strip()).strip()
                if conteudo:
                    norm = secao_atual.lower().rstrip(":_ ")
                    if norm not in _SECOES_IGNORADAS:
                        secoes.append((secao_atual, conteudo))
            secao_atual = titulo
            conteudo_atual = []
        elif secao_atual is not None:
            conteudo_atual.append(linha)

    # Fecha última seção
    if secao_atual and conteudo_atual:
        conteudo = "\n".join(l for l in conteudo_atual if l.strip()).strip()
        if conteudo:
            norm = secao_atual.lower().rstrip(":_ ")
            if norm not in _SECOES_IGNORADAS:
                secoes.append((secao_atual, conteudo))

    return secoes


# ── Geração do PDF ────────────────────────────────────────────────────────────

def gerar_pdf_candidatura(dados: DadosCandidatura) -> bytes:
    """Gera PDF de currículo adaptado para a vaga. Retorna bytes."""
    import fitz  # PyMuPDF

    doc = fitz.open()

    COR_PRIMARIA  = (0.24, 0.32, 0.71)
    COR_TEXTO     = (0.10, 0.10, 0.10)
    COR_SUBTEXTO  = (0.38, 0.38, 0.38)
    COR_LINHA     = (0.85, 0.85, 0.92)
    MARGEM_X      = 55
    MARGEM_X_DIR  = 540
    LARGURA       = 595
    ALTURA        = 842

    # página atual e cursor y — mutáveis via lista para escopo não-local
    state = {"page": None, "y": 30.0}

    def nova_pagina():
        pg = doc.new_page(width=LARGURA, height=ALTURA)
        pg.draw_rect(fitz.Rect(0, 0, LARGURA, 8), color=COR_PRIMARIA, fill=COR_PRIMARIA)
        state["page"] = pg
        state["y"] = 30.0

    def check_overflow(espaco=40):
        if state["y"] > ALTURA - espaco:
            nova_pagina()

    def txt(texto, size=10, cor=None, bold=False, x=None):
        if not texto:
            state["y"] += size * 0.5
            return
        cor = cor or COR_TEXTO
        fn = "hebo" if bold else "helv"
        x_ = x if x is not None else MARGEM_X
        state["page"].insert_text((x_, state["y"]), str(texto), fontname=fn, fontsize=size, color=cor)
        state["y"] += size * 1.4

    def secao(titulo):
        state["y"] += 8
        check_overflow(60)
        state["page"].insert_text(
            (MARGEM_X, state["y"]), titulo.upper(),
            fontname="hebo", fontsize=9.5, color=COR_PRIMARIA,
        )
        state["y"] += 5
        state["page"].draw_line(
            (MARGEM_X, state["y"]), (MARGEM_X_DIR, state["y"]),
            color=COR_PRIMARIA, width=0.8,
        )
        state["y"] += 10

    def linha_sutil():
        state["page"].draw_line(
            (MARGEM_X, state["y"]), (MARGEM_X_DIR, state["y"]),
            color=COR_LINHA, width=0.4,
        )
        state["y"] += 8

    def bloco(texto, size=9.5, cor=None, recuo=0):
        if not texto:
            return
        cor = cor or COR_TEXTO
        mw = MARGEM_X_DIR - MARGEM_X - recuo
        chars = max(30, int(mw / (size * 0.52)))
        for paragrafo in str(texto).split("\n"):
            paragrafo = paragrafo.strip()
            if not paragrafo:
                state["y"] += size * 0.6
                continue
            for linha in textwrap.wrap(paragrafo, width=chars) or [paragrafo]:
                check_overflow(20)
                state["page"].insert_text(
                    (MARGEM_X + recuo, state["y"]), linha,
                    fontname="helv", fontsize=size, color=cor,
                )
                state["y"] += size * 1.45

    # ── Início ────────────────────────────────────────────────────────────────
    nova_pagina()

    # Header
    txt(dados.nome_candidato, size=20, bold=True, cor=COR_PRIMARIA)
    txt(dados.titulo_vaga or dados.cargo_desejado, size=11, cor=COR_SUBTEXTO)
    state["y"] += 3
    contato = "  ·  ".join(p for p in [dados.email, dados.telefone] if p)
    if contato:
        txt(contato, size=9, cor=COR_SUBTEXTO)
    state["y"] += 4
    state["page"].draw_line(
        (MARGEM_X, state["y"]), (MARGEM_X_DIR, state["y"]),
        color=COR_LINHA, width=0.5,
    )
    state["y"] += 10

    # Objetivo Profissional
    if dados.resumo_personalizado:
        secao("Objetivo Profissional")
        bloco(dados.resumo_personalizado, size=9.5)
        state["y"] += 4

    # Competências
    if dados.skills:
        secao("Competências")
        skills_clean = [str(s).strip() for s in dados.skills if str(s).strip()]
        linha_sk = ""
        for sk in skills_clean:
            sep = "   ·   " if linha_sk else ""
            candidato = linha_sk + sep + sk
            if len(candidato) > 65 and linha_sk:
                txt(linha_sk, size=9.5)
                linha_sk = sk
            else:
                linha_sk = candidato
        if linha_sk:
            txt(linha_sk, size=9.5)
        state["y"] += 4

    # Experiência Profissional
    if dados.experiencias:
        secao("Experiência Profissional")
        for i, exp in enumerate(dados.experiencias):
            check_overflow(70)
            cargo_exp   = str(exp.get("cargo", "") or "").strip()
            empresa_exp = str(exp.get("empresa", "") or "").strip()
            periodo_exp = str(exp.get("periodo", "") or "").strip()
            descricao   = str(exp.get("descricao", "") or "").strip()

            txt(cargo_exp, size=10, bold=True)
            sub = "  ·  ".join(p for p in [empresa_exp, periodo_exp] if p)
            if sub:
                txt(sub, size=9, cor=COR_SUBTEXTO)
            if descricao:
                bloco(descricao, size=9, recuo=4)
            state["y"] += 4
            if i < len(dados.experiencias) - 1:
                linha_sutil()

    # Formação Acadêmica
    if dados.formacao:
        secao("Formação Acadêmica")
        for form in dados.formacao:
            check_overflow(50)
            grau   = str(form.get("grau", "") or "").strip()
            curso  = str(form.get("curso", "") or "").strip()
            inst   = str(form.get("instituicao", "") or "").strip()
            ano    = str(form.get("ano", "") or "").strip()

            titulo_form = " — ".join(p for p in [grau, curso] if p) or curso
            txt(titulo_form, size=10, bold=True)
            sub_form = "  ·  ".join(p for p in [inst, ano] if p)
            if sub_form:
                txt(sub_form, size=9, cor=COR_SUBTEXTO)
            state["y"] += 4

    # Seções extras do cv_texto (Idiomas, Certificações, Projetos, etc.)
    extras = _detectar_secoes_extras(dados.cv_texto)
    for titulo_extra, conteudo_extra in extras:
        secao(titulo_extra)
        bloco(conteudo_extra, size=9.5)
        state["y"] += 4

    # Rodapés
    tag = "Candidatura simplificada" if dados.simplificada else "Candidatura"
    rodape = f"z3ndocs  ·  {tag}: {dados.titulo_vaga} · {dados.empresa}"
    total_pgs = len(doc)
    for i, pg in enumerate(doc):
        pg.draw_line(
            (MARGEM_X, ALTURA - 25), (MARGEM_X_DIR, ALTURA - 25),
            color=COR_LINHA, width=0.3,
        )
        pg.insert_text(
            (MARGEM_X, ALTURA - 14),
            f"{rodape}  ·  Página {i+1} de {total_pgs}",
            fontname="helv", fontsize=7.5, color=COR_SUBTEXTO,
        )

    return doc.tobytes()
