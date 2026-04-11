---
name: system-defaults-simplenamespace
description: Por que system defaults de AudioConfig usam SimpleNamespace em vez de instância ORM
type: feedback
---

# Decisão: SimpleNamespace para system defaults

**Regra:** Quando não existe nenhuma `AudioConfig` no banco (nem de agente, nem de tenant), retornar `types.SimpleNamespace(id=None, ...)` com os valores padrão — não tentar instanciar `AudioConfig()` ou `AudioConfig.__new__(AudioConfig)`.

**Why:** SQLAlchemy injeta `_sa_instance_state` via `__init__`. Criar um objeto ORM fora de uma sessão (sem `session.add()`) leva a erros como `TypeError: AudioConfig.__new__() takes 1 positional argument but 2 were given` ou comportamentos imprevisíveis com lazy loading.

**How to apply:** Qualquer módulo que precise de "defaults de sistema" sem banco deve usar `types.SimpleNamespace`. Testar explicitamente que o objeto retornado tem `id=None` para saber que não é um registro real. O `AudioService.resolver_config()` já faz isso como terceiro passo da cascata.
