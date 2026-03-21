# Fase 7 — Streamlit: Agent Selector, File Upload e Loading State

## Objetivo

Atualizar a UI Streamlit (`src/docagent/ui.py`) para expor as capacidades já implementadas no backend:

1. **Agent selector** — dropdown para escolher o agente antes de enviar mensagem
2. **File upload** — widget para enviar PDFs para o RAG da sessão
3. **Loading state** — spinner enquanto aguarda a primeira resposta do LLM

Nenhum backend é alterado. Apenas `ui.py`.

---

## Estrutura de arquivos

```
src/docagent/
└── ui.py    ← único arquivo modificado
```

---

## Agent Selector

Busca `GET /agents` na inicialização e exibe `st.selectbox` na sidebar.
O `agent_id` selecionado é enviado no body do POST /chat.

```python
@st.cache_data(ttl=60)
def fetch_agents(api_url: str) -> list[dict]:
    """Cache por 60s para não re-buscar a cada interação."""
    try:
        response = httpx.get(f"{api_url}/agents", timeout=5)
        return response.json()
    except httpx.HTTPError:
        return []

# Sidebar
agents = fetch_agents(API_URL)
agent_options = {a["name"]: a["id"] for a in agents}
selected_name = st.sidebar.selectbox("🤖 Agente", list(agent_options.keys()))
selected_agent_id = agent_options.get(selected_name, "doc-analyst")
```

---

## File Upload

Widget `st.file_uploader` na sidebar. Quando um arquivo novo é detectado
(comparando por nome com o último uploaded), faz POST multipart para `/documents/upload`.

```python
uploaded_file = st.sidebar.file_uploader("📎 Carregar PDF", type=["pdf"])

if uploaded_file and uploaded_file.name != st.session_state.get("last_upload"):
    with st.sidebar.spinner("Indexando documento..."):
        try:
            resp = httpx.post(
                f"{API_URL}/documents/upload",
                files={"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")},
                data={"session_id": st.session_state.session_id},
                timeout=60,
            )
            result = resp.json()
            st.session_state.last_upload = uploaded_file.name
            st.sidebar.success(f"✅ {result['chunks']} chunks indexados")
        except httpx.HTTPError as e:
            st.sidebar.error(f"⚠️ Erro no upload: {e}")
```

---

## Loading State

Usa `st.spinner` para cobrir o período entre o envio da requisição e o
recebimento do primeiro evento SSE. O spinner é removido automaticamente
quando o bloco `with` termina.

```python
with st.chat_message("assistant"):
    placeholder = st.empty()
    status_placeholder = st.empty()
    full_response = ""

    with st.spinner("Consultando agente..."):
        with httpx.Client(timeout=120) as client:
            with client.stream("POST", f"{API_URL}/chat", json={
                "question": prompt,
                "session_id": st.session_state.session_id,
                "agent_id": selected_agent_id,      # novo campo
            }) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    ...  # parsing SSE igual ao atual
```

O `st.spinner` cobre o tempo de "warm-up" antes do primeiro `step` ou `answer`
chegar. Assim que qualquer evento chega, o contexto do spinner já está ativo
mas os placeholders abaixo começam a ser preenchidos — efeito visual correto.

---

## Estado da sessão — novos campos

```python
# Já existentes
st.session_state.session_id
st.session_state.messages

# Novos
st.session_state.last_upload   # nome do último arquivo uploadado (evita re-upload)
```

---

## Sidebar — layout final

```
[ Sessão ]
  abc123...
  [ 🗑️ Limpar conversa ]

[ 🤖 Agente ]
  ▼ Analista de Documentos

[ 📎 Carregar PDF ]
  Arraste ou clique para selecionar
  ✅ relatorio.pdf — 42 chunks indexados

──────────
Ferramentas disponíveis:
🔍 rag_search — busca nos documentos
🌐 web_search — busca na internet
```

---

## Plano de verificação

```bash
# Rodar a API
uv run uvicorn docagent.api:app --reload

# Rodar a UI
uv run streamlit run src/docagent/ui.py

# Verificar manualmente:
# 1. Sidebar mostra dropdown com os agentes retornados por GET /agents
# 2. Upload de um PDF mostra "N chunks indexados"
# 3. Enviar mensagem mostra spinner até a primeira resposta
# 4. Trocar agente e enviar mensagem — agent_id correto aparece nos logs da API
```

---

## Princípios aplicados

| Princípio | Onde |
|---|---|
| **Cache** | `@st.cache_data(ttl=60)` evita GET /agents a cada render |
| **Idempotência** | Compara `uploaded_file.name` com `last_upload` para não re-indexar |
| **Zero mudanças no backend** | Fase puramente de UI, sem tocar em API, services ou routers |
