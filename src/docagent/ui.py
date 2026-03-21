"""
Fase 7 — Interface Streamlit atualizada.

Novidades em relacao a Fase 4:
- Agent selector: dropdown que busca GET /agents e envia agent_id no chat
- File upload: widget PDF na sidebar que posta em POST /documents/upload
- Loading state: spinner enquanto aguarda o primeiro evento SSE

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

if "last_upload" not in st.session_state:
    st.session_state.last_upload = None

# ---------------------------------------------------------------------------
# Busca de agentes (cacheada)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60)
def fetch_agents(api_url: str) -> list[dict]:
    """Busca lista de agentes disponíveis. Cache de 60s."""
    try:
        response = httpx.get(f"{api_url}/agents", timeout=5)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return []

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
        st.session_state.last_upload = None
        st.rerun()

    st.divider()

    # Agent selector
    agents = fetch_agents(API_URL)
    if agents:
        agent_options = {a["name"]: a["id"] for a in agents}
        selected_name = st.selectbox("🤖 Agente", list(agent_options.keys()))
        selected_agent_id = agent_options[selected_name]
    else:
        st.caption("⚠️ Nao foi possivel carregar agentes")
        selected_agent_id = "doc-analyst"

    st.divider()

    # File upload
    uploaded_file = st.file_uploader("📎 Carregar PDF", type=["pdf"])
    if uploaded_file and uploaded_file.name != st.session_state.last_upload:
        with st.spinner("Indexando documento..."):
            try:
                resp = httpx.post(
                    f"{API_URL}/documents/upload",
                    files={"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")},
                    data={"session_id": st.session_state.session_id},
                    timeout=60,
                )
                resp.raise_for_status()
                result = resp.json()
                st.session_state.last_upload = uploaded_file.name
                st.success(f"✅ {result['chunks']} chunks indexados")
            except httpx.HTTPError as e:
                st.error(f"⚠️ Erro no upload: {e}")

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
            with st.spinner("Consultando agente..."):
                with httpx.Client(timeout=120) as client:
                    with client.stream(
                        "POST",
                        f"{API_URL}/chat",
                        json={
                            "question": prompt,
                            "session_id": st.session_state.session_id,
                            "agent_id": selected_agent_id,
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
