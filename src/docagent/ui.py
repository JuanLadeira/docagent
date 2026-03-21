"""
Fase 4 — Interface Streamlit para o DocAgent.

Consome a API FastAPI via SSE, exibindo a resposta do agente
em tempo real conforme os eventos chegam.

Para rodar: uv run streamlit run src/docagent/ui.py
"""
import os
import json
import uuid
import httpx
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

# ---------------------------------------------------------------------------
# Configuracao da pagina
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="DocAgent",
    page_icon="📄",
    layout="centered",
)

st.title("📄 DocAgent")
st.caption("Agente de pesquisa em documentos com RAG + busca na web")

# ---------------------------------------------------------------------------
# Estado da sessao
# ---------------------------------------------------------------------------

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Sessao")
    st.code(st.session_state.session_id[:8] + "...", language=None)

    if st.button("🗑️ Limpar conversa", use_container_width=True):
        try:
            httpx.delete(f"{API_URL}/session/{st.session_state.session_id}", timeout=5)
        except httpx.HTTPError:
            pass
        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())
        st.rerun()

    st.divider()
    st.caption("**Ferramentas disponíveis:**")
    st.caption("🔍 rag_search — busca nos documentos")
    st.caption("🌐 web_search — busca na internet")

# ---------------------------------------------------------------------------
# Historico de mensagens
# ---------------------------------------------------------------------------

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ---------------------------------------------------------------------------
# Input e streaming
# ---------------------------------------------------------------------------

if prompt := st.chat_input("Digite sua pergunta..."):
    # Exibe mensagem do usuario
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Exibe resposta do agente com streaming
    with st.chat_message("assistant"):
        placeholder = st.empty()
        status_placeholder = st.empty()
        full_response = ""

        try:
            with httpx.Client(timeout=120) as client:
                with client.stream(
                    "POST",
                    f"{API_URL}/chat",
                    json={
                        "question": prompt,
                        "session_id": st.session_state.session_id,
                    },
                ) as response:
                    response.raise_for_status()

                    for line in response.iter_lines():
                        if not line.startswith("data:"):
                            continue

                        payload = line[len("data:"):].strip()
                        try:
                            event = json.loads(payload)
                        except json.JSONDecodeError:
                            continue

                        event_type = event.get("type")

                        if event_type == "step":
                            # Mostra progresso intermediario em italico
                            status_placeholder.markdown(f"_{event['content']}_")

                        elif event_type == "answer":
                            # Exibe a resposta final
                            full_response = event["content"]
                            status_placeholder.empty()
                            placeholder.markdown(full_response)

                        elif event_type == "done":
                            break

        except httpx.ConnectError:
            full_response = "⚠️ Nao foi possivel conectar à API. Verifique se o servidor esta rodando."
            placeholder.error(full_response)

        except httpx.HTTPStatusError as e:
            full_response = f"⚠️ Erro na API: {e.response.status_code}"
            placeholder.error(full_response)

    if full_response:
        st.session_state.messages.append({"role": "assistant", "content": full_response})
