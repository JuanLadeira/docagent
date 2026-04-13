# Decisão: Player de áudio usa fetch+blob, não src direto

**Fase:** 21 (fix)
**Data:** 2026-04-12

---

## Problema

O elemento `<audio controls :src="/api/atendimentos/media/{id}">` não funcionava porque o browser faz um GET direto para o `src`, sem enviar o header `Authorization: Bearer {token}`. O endpoint de mídia requer autenticação, então retornava 401.

## Alternativas consideradas

1. **Endpoint público de mídia** — risco de segurança (qualquer um acessa com o ID)
2. **Token na query string** — tokens em URLs ficam em logs de servidor/proxy
3. **fetch() com auth + blob URL** — ✅ escolhida

## Decisão

No `AtendimentoView.vue`, ao carregar mensagens de áudio, fazer `fetch()` com o header correto e criar um `URL.createObjectURL(blob)`. Usar esse blob URL como `src` do `<audio>`.

```typescript
async function carregarAudio(mensagemId: number): Promise<void> {
  const token = sessionStorage.getItem('token') ?? ''
  const res = await fetch(`/api/atendimentos/media/${mensagemId}`, {
    headers: { Authorization: `Bearer ${token}` }
  })
  const blob = await res.blob()
  audioBlobUrls.value[mensagemId] = URL.createObjectURL(blob)
}
```

## Consequência

- Blob URLs são criados por sessão e não persistem entre reloads (comportamento correto)
- Mensagens carregadas via API (ao abrir atendimento) pré-carregam os blobs
- Mensagens chegando via SSE disparam o carregamento assim que o `mensagem_id` real chega
- O backend precisa incluir `mensagem_id` real nos payloads SSE (feito na mesma Fase 21)
