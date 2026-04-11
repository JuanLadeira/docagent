---
name: fk-agente-tablename
description: O tablename do modelo Agente é "agente" (singular), não "agentes"
type: feedback
---

# Decisão: FK para "agente", não "agentes"

**Regra:** Ao escrever FKs ou queries que referenciam o modelo `Agente`, usar `"agente.id"` — não `"agentes.id"`.

**Why:** O modelo define `__tablename__ = "agente"`. SQLAlchemy valida o nome da tabela em runtime ao criar o mapper. Usar `"agentes.id"` lança `NoReferencedTableError` ao subir a aplicação.

**How to apply:** Antes de escrever qualquer `ForeignKey("X.id")`, grep pelo `__tablename__` do modelo alvo. Não assumir plural automático. Mesmo convenção se aplica a outros modelos: `tenant`, `usuario`, `mcp_server`, `audio_config`.
