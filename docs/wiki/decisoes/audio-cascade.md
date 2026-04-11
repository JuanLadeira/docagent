---
name: audio-cascade
description: Config de áudio resolve em cascata: agente → tenant → system defaults
type: project
---

# Decisão: Cascata de Configuração de Áudio

**Regra:** `AudioService.resolver_config(agente_id, tenant_id, db)` sempre tenta na ordem: (1) config específica do agente, (2) config padrão do tenant (`agente_id IS NULL`), (3) `types.SimpleNamespace` com system defaults.

**Why:** Permite que o tenant configure um padrão global (ex: STT habilitado com Whisper base) e apenas agentes específicos sobrescrevam. Sem essa cascata, cada agente precisaria ter sua config explícita, ou o código teria lógica espalhada em vários lugares.

**How to apply:** Ao desenvolver qualquer funcionalidade que depende de configuração por agente com fallback para tenant, usar o mesmo padrão de cascata. Criar método `resolver_config` no service correspondente. O nível 3 (system defaults) sempre retorna `SimpleNamespace` com `id=None`.

A tabela `audio_config` implementa isso via `UniqueConstraint("tenant_id", "agente_id")` — o registro com `agente_id=NULL` é o padrão do tenant.
