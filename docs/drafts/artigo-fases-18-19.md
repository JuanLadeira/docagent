# Voz, memória e esquema: do áudio ao histórico persistido (fases 18–19)

---

No artigo anterior, o sistema tinha planos com quotas, atendimento multi-canal, integração com WhatsApp e Telegram, e um painel de operadores em tempo real via SSE. O que ele não tinha era memória além de uma sessão — cada conversa com o agente era descartada ao fechar o browser. E não tinha voz.

As fases 18 e 19 resolveram esses dois problemas, e o processo de implementar cada um revelou algo diferente sobre como construir sistemas que lidam com mídia e com estado.

O esquema completo do banco de dados está em: [dbdiagram.io/d/Zendocs](https://dbdiagram.io/d/Zendocs-66a1cabd8b4bb5230e49ea4c)

---

## FASE 18 — Áudio: quando o Telegram te manda um voice note

A demanda surgiu de um caso real: usuários mandavam áudios no Telegram e o bot simplesmente ignorava. O evento chegava no webhook, o campo `voice` estava no payload, mas não havia nada para processar.

Adicionar suporte a áudio exigiu duas tecnologias distintas — uma para ouvir (STT) e uma para falar (TTS) — e uma decisão arquitetural sobre onde configurá-las.

### Speech-to-Text com faster-whisper

O Whisper da OpenAI é o modelo de referência para transcrição. O `faster-whisper` é uma reimplementação que usa CTranslate2 para rodar em CPU a 4x a velocidade do original, com metade da VRAM se usado em GPU.

O fluxo no webhook do Telegram:

```
Webhook recebe { voice: { file_id: "..." } }
  → download do arquivo .ogg via Bot API
  → transcrição com faster-whisper
  → texto transcrito entra na pipeline do agente
  → resposta do agente (texto)
```

O detalhe técnico que apareceu: o Telegram entrega áudios em formato `.ogg` com codec Opus. O Whisper espera `.wav` ou `.mp3`. A conversão é feita com `ffmpeg` — um binário de sistema, não uma biblioteca Python. O Dockerfile precisou ser atualizado:

```dockerfile
RUN apt-get install -y ffmpeg
RUN pip install faster-whisper
```

Isso parece trivial até você perceber que o tamanho do container aumentou ~1.5GB por causa do modelo Whisper. A decisão foi baixar o modelo durante o primeiro uso (`download_root="/tmp/whisper"`) em vez de empacotar no build — o container sobe mais rápido, a primeira transcrição é mais lenta.

**O problema da qualidade da transcrição.** O modelo padrão inicial era `base` — 74M parâmetros, o menor entre os modelos Whisper. Para PT-BR em condições reais (ruído de fundo, sotaque, fala rápida), o `base` alucina: transcreve palavras que não existem, corta sílabas, troca termos semelhantes. A hierarquia em qualidade é `tiny → base → small → medium → large-v3`. O salto de `base` para `small` (244M parâmetros) é desproporcional ao custo: a qualidade melhora significativamente, e o tempo de transcrição numa CPU moderna fica entre 3–5 segundos — aceitável para mensagens de voz curtas.

Dois parâmetros adicionais fizeram diferença na prática:

```python
segments, info = model.transcribe(
    tmp_path,
    language="pt",
    beam_size=5,
    vad_filter=True,
    vad_parameters={"min_silence_duration_ms": 500},
)
```

`vad_filter=True` aplica Voice Activity Detection antes da transcrição: detecta e remove os trechos de silêncio no início e no fim do áudio. Sem isso, o Whisper tenta transcrever silêncio — e alucina. `beam_size=5` é o padrão do decoder, mas torná-lo explícito evita surpresas se o valor padrão mudar em versões futuras.

O `info` retornado pelo `transcribe` tem o `language_probability` — a confiança do modelo no idioma detectado. Logá-lo é útil para diagnosticar transcrições ruins: se a probabilidade está abaixo de 80%, provavelmente o áudio tem muito ruído ou o usuário falou em outro idioma.

### Text-to-Speech com Piper

Para a resposta em áudio, escolhi o Piper — um sintetizador de voz local da Mozilla que roda sem GPU, com modelos de ~66MB por idioma. A voz padrão configurada foi `pt_BR-faber-medium`.

O Piper é um binário, não uma biblioteca Python. A integração foi via `subprocess`:

```python
process = await asyncio.create_subprocess_exec(
    "piper",
    "--model", model_path,
    "--output_file", output_path,
    stdin=asyncio.subprocess.PIPE,
    stdout=asyncio.subprocess.PIPE,
)
stdout, _ = await process.communicate(input=text.encode())
```

O binário lê o texto da stdin e grava o `.wav` no caminho especificado. Depois, o backend envia o arquivo de áudio de volta ao usuário via `sendAudio` da Bot API do Telegram.

### AudioConfig: configuração por agente

A pergunta de design foi: onde guardar a configuração de STT/TTS? Variável de ambiente não funciona — tenants diferentes podem querer configurações diferentes. Campo no modelo `Agente` mistura responsabilidades.

A solução foi uma tabela dedicada `audio_config` com chave única `(tenant_id, agente_id)`. Se `agente_id` é NULL, é a configuração padrão do tenant. Cada agente pode ter sua própria configuração ou herdar a do tenant.

Os campos que importam:

```
stt_habilitado   → bool
tts_habilitado   → bool
stt_provider     → faster_whisper | openai
tts_provider     → piper | openai | elevenlabs
modo_resposta    → audio_apenas | texto_apenas | audio_e_texto
```

O `modo_resposta` controla o que o bot envia de volta: só texto, só áudio, ou os dois. Alguns usuários preferem ouvir a resposta, outros precisam do texto para copiar um link ou um número.

O frontend ganhou um formulário `AudioConfigForm` com tabs específicas em Configurações e em cada agente — o mesmo componente instanciado com contextos diferentes.

### O bug que o logging revelou: áudio não aparecia na UI

Depois da implementação inicial, os áudios recebidos pelo Telegram não apareciam no painel de atendimento — e as respostas em TTS também não. O bug estava em `_processar_update`, a função central do webhook.

O caminho de áudio tinha um fluxo separado do caminho de texto:

```python
# caminho de áudio
if voice_or_audio and not conteudo:
    # ... baixa, transcreve ...
    answer = await _executar_agente_telegram(agente_obj, conteudo, ...)
    await _enviar_resposta_telegram(bot_token, chat_id, answer, audio_config)
    return  # ← sai aqui, sem salvar, sem emitir SSE
```

O `return` antecipado pulava toda a lógica que o caminho de texto executava: criar/recuperar o atendimento, salvar `MensagemAtendimento` no banco, e emitir os eventos SSE que o frontend escuta. O agente respondia, o Telegram recebia — mas o painel do operador não sabia que nada tinha acontecido.

A correção foi remover o bloco inline e o `return`, deixando a transcrição cair no fluxo normal. `audio_config` ficou na variável do escopo externo e foi propagado até `_executar_agente_e_salvar`, que agora usa `_enviar_resposta_telegram` em vez do `/sendMessage` simples:

```python
# caminho de áudio — apenas transcreve e sai do bloco
if voice_or_audio and not conteudo:
    # ... baixa, transcreve ...
    conteudo = transcricao  # cai no fluxo normal abaixo

# fluxo normal: cria atendimento, salva mensagem, emite SSE
async with AsyncSessionLocal() as db:
    # ... upsert atendimento ...
    conteudo_salvo = f"[Áudio] {conteudo}" if voice_or_audio else conteudo
    db.add(MensagemAtendimento(..., conteudo=conteudo_salvo))
    await db.commit()

await atendimento_sse_manager.broadcast(atendimento_id, {
    "type": "NOVA_MENSAGEM",
    "origem": "CONTATO",
    "conteudo": conteudo_salvo,  # aparece no painel do operador
})

await _executar_agente_e_salvar(..., audio_config=audio_config)
# agora usa _enviar_resposta_telegram → TTS funciona no caminho normal
```

O prefixo `[Áudio]` na mensagem salva é um marcador para o operador: indica que aquela mensagem chegou como voz e foi transcrita. O agente recebe o texto puro (sem o prefixo) para não contaminar o contexto.

---

## FASE 19 — Histórico: o que significa "lembrar" uma conversa

Até a fase 19, a "memória" do sistema era o `SessionManager` — um dicionário em memória que guardava o histórico da conversa enquanto o processo estava vivo. Reiniciar o servidor, fechar o browser, ou acessar de outro dispositivo: histórico perdido.

Persistir isso no banco parece simples. Na prática, revelou três problemas independentes: onde guardar, como carregar, e como mostrar.

### O schema: duas tabelas, uma relação clara

```
conversa
  ├── tenant_id, usuario_id, agente_id  (FK)
  ├── titulo        (gerado pelo LLM após o 1º turn)
  ├── arquivada     (soft delete)
  └── updated_at    (atualizado a cada mensagem — para ordenação)

mensagem_conversa
  ├── conversa_id   (FK)
  ├── role          (user | assistant | tool | system)
  ├── conteudo      (text)
  ├── tool_name     (preenchido quando role = tool)
  └── tokens_entrada, tokens_saida
```

O índice `(usuario_id, updated_at)` na tabela `conversa` existe por uma razão: a query mais comum é "últimas N conversas desse usuário, ordenadas por atividade". Sem esse índice, cada listagem faz full scan.

### O evento SSE `meta`: comunicar o ID antes de qualquer chunk

O endpoint `/chat` precisa criar uma conversa nova (quando não existe `conversa_id` no request) e informar o cliente qual ID foi criado — para que os próximos requests reusem a mesma conversa.

O problema é que o endpoint retorna um `StreamingResponse`. Não tem como adicionar um campo no header depois que o stream começou. A solução foi adicionar um evento SSE especial *antes* dos chunks do agente:

```python
async def managed_stream():
    yield f"data: {json.dumps({'type': 'meta', 'conversa_id': conversa.id})}\n\n"
    async for chunk in agent_stream:
        yield chunk
```

O cliente captura esse evento e salva o `conversa_id` localmente. Todos os requests subsequentes na mesma sessão incluem esse ID.

A posição importa: o `meta` precisa ser o *primeiro* evento, não o último. Se vier depois do `done`, o cliente já encerrou a conexão SSE.

### Reconstruir o histórico: LangChain espera tipos específicos

Salvar mensagens como texto é simples. Carregar de volta para o LangGraph é onde aparece a fricção.

O LangGraph trabalha com `HumanMessage`, `AIMessage`, `ToolMessage` — não com strings. A conversão exigiu um helper que mapeia o campo `role` do banco para o tipo correto:

```python
def _to_langchain_message(m: MensagemConversa) -> BaseMessage:
    if m.role == "user":
        return HumanMessage(content=m.conteudo)
    elif m.role == "assistant":
        return AIMessage(content=m.conteudo)
    elif m.role == "tool":
        return ToolMessage(content=m.conteudo, tool_call_id=m.tool_name or "")
    else:
        return SystemMessage(content=m.conteudo)
```

O detalhe do `ToolMessage`: ele exige um `tool_call_id`, não só o conteúdo. Salvar o `tool_name` no banco foi necessário para essa reconstrução.

### Gerar título sem bloquear o stream

Após o primeiro turn de uma conversa, quero gerar um título automático baseado na pergunta do usuário. Mas gerar título é uma chamada ao LLM — pode levar 2-3 segundos. O cliente não deve esperar isso para receber a resposta.

A solução foi `asyncio.create_task()`:

```python
if await svc.contar_mensagens(conversa.id) == 1:
    asyncio.create_task(_gerar_titulo_bg(conversa.id, question, db))
```

A task roda em background, sem bloquear o stream. O título aparece na sidebar na próxima vez que a lista é carregada — não instantaneamente, mas a resposta chega imediatamente.

### A sidebar: dois modos, um componente

O frontend ganhou uma sidebar com duas tabs: **Conversas** (histórico) e **Docs** (documentos do agente).

A lista de conversas é agrupada por data:

```
Hoje
  └── Perguntas sobre o contrato de locação
Ontem
  └── Análise do relatório financeiro Q3
Esta semana
  └── Configuração do webhook Telegram
```

O scroll infinito foi implementado com um `@scroll` handler no container da lista — quando o usuário chega a 100px do final, carrega a próxima página via `GET /api/chat/conversas?page=N`.

O comportamento mais interessante foi o que acontece ao trocar de agente na aba Docs. Fazia sentido que trocar o agente ativo abrisse automaticamente a última conversa com ele — ou criasse uma nova se não existisse nenhuma:

```typescript
async function selectAgentFromDocs(id: string) {
  chat.selectedAgentId = id
  const res = await api.listConversas({ agente_id: Number(id), page: 1, page_size: 1 })
  if (res.data.items.length > 0) {
    await chat.carregarConversa(res.data.items[0].id)
  } else {
    await chat.resetSession()  // nova conversa no próximo envio
  }
  sidebarTab.value = 'conversas'  // troca a aba automaticamente
}
```

Não há endpoint "criar conversa vazia" — a conversa só existe depois do primeiro turn. O `resetSession()` cria a sessão em branco; a conversa é criada no backend quando o usuário enviar a primeira mensagem.

---

## O que as fases 18 e 19 ensinaram

**Binários são dependências como qualquer outra.** O `ffmpeg` e o `piper` são binários do sistema — não aparecem no `pyproject.toml`, não têm versão no lockfile, e podem quebrar silenciosamente se ausentes. Documentar no `Dockerfile` e no `.env.example` é a única garantia.

**O modelo padrão importa mais que o código.** Implementar STT com o modelo `base` e pensar "funciona, deploy" foi um erro. O `base` alucina em PT-BR. A transcrição ficou ruim não por causa do código — o código estava correto — mas por causa do parâmetro default. Mudar `"base"` para `"small"` e adicionar `vad_filter=True` resolveu a maior parte dos problemas sem tocar na arquitetura. Parâmetros de modelo têm impacto maior que refatorações de código.

**Fluxos paralelos para o mesmo recurso divergem.** O webhook tinha dois caminhos: texto e áudio. O caminho de texto salvava mensagens e emitia SSE. O caminho de áudio executava o agente e retornava — sem salvar, sem emitir. Funcionalmente pareciam equivalentes: o Telegram recebia a resposta. Mas o painel do operador ficou cego para o caminho de áudio. O bug foi invisível por um tempo justamente porque o Telegram funcionava. A correção foi unificar os dois caminhos: a transcrição vira texto e cai no fluxo normal. Dois fluxos para o mesmo recurso quase sempre divergem com o tempo — é melhor um único fluxo com parâmetro diferente.

**Eventos SSE têm ordem e semântica.** O evento `meta` com `conversa_id` precisava vir antes dos chunks do agente. Isso não é uma convenção arbitrária — é o único momento em que o cliente pode capturar o ID sem correr o risco de ter perdido a conexão. Eventos SSE têm posição significativa.

**Tarefas de background não são gambiarra.** Gerar título em background via `asyncio.create_task()` pareceu um atalho. Na prática, é o padrão correto: separar o caminho crítico (resposta ao usuário) de tarefas que podem ser eventual e assincronamente. O usuário não precisa esperar o título para ler a resposta.

**Soft delete é uma decisão de produto.** Arquivar uma conversa em vez de deletar significa que ela pode ser recuperada. Mas também significa que a query de listagem precisa filtrar `arquivada = false` em toda parte — se esquecer um lugar, conversas arquivadas reaparecem. A consistência precisa ser mantida em todos os pontos de leitura.

**Modelar o banco antes de escrever código.** O DBML do schema completo foi escrito depois de todas as tabelas existirem — mas deveria ter sido escrito antes. Ver todas as relações num diagrama torna óbvio o que seria obscuro no código: por que `audio_config` tem `(tenant_id, agente_id)` como chave única, por que `conversa` tem um índice composto em `(usuario_id, updated_at)`, por que `atendimento` tem FKs para duas instâncias diferentes com SET NULL.

**O que ainda falta no áudio.** A UI do painel de operadores mostra mensagens de voz como texto transcrito — não há player de áudio. Para reproduzir o áudio original do contato, o backend precisaria salvar o `file_id` do Telegram na mensagem e expor um endpoint proxy que baixa o arquivo sob demanda. Para reproduzir o áudio gerado pelo TTS, precisaria armazenar o `.ogg` gerado. Ambos são possíveis, mas exigem mudança no schema (`mensagem_atendimento` ganharia campos `tipo` e `media_url`) e um endpoint de streaming de mídia. A prioridade foi fazer o texto aparecer primeiro; o player é a próxima iteração.

---

O repositório está em github.com/JuanLadeira/docagent. O diagrama completo do banco em [dbdiagram.io/d/Zendocs](https://dbdiagram.io/d/Zendocs-66a1cabd8b4bb5230e49ea4c).
