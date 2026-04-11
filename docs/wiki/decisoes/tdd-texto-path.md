---
name: tdd-texto-path
description: O path de texto nos webhooks WhatsApp/Telegram foi mantido inline (não refatorado) para não quebrar testes existentes
type: feedback
---

# Decisão: path de texto mantido inline nos webhooks

**Regra:** Ao adicionar o path de áudio nos webhooks (`whatsapp/router.py`, `telegram/router.py`), o path de texto existente **não** foi refatorado para usar helpers extraídos. O áudio usa funções helper novas (`_executar_agente_telegram`, etc.); o texto continua inline.

**Why:** Os testes de regressão existentes mockam comportamentos específicos do path inline. Refatorar o path de texto exigiria atualizar todos esses mocks — risco alto de quebrar testes por mudança cirúrgica de escopo. A abordagem "cirúrgica" foi preferida: só adicionar, não modificar o que já funciona.

**How to apply:** Se no futuro quiser unificar os dois paths, fazer como task separada com refactor completo dos testes correspondentes. Não misturar com uma feature sprint.
