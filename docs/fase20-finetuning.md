# Fase 20 — Fine-Tuning Pipeline

## Objetivo

Permitir que tenants treinem modelos customizados a partir dos seus próprios dados de atendimento. O resultado é um modelo menor e mais preciso para o domínio do cliente — que pode ser selecionado como LLM de qualquer agente da plataforma.

---

## Conceito: RAG vs Fine-Tuning

| | RAG (como está hoje) | Fine-Tuning |
|--|---------------------|-------------|
| Como funciona | Busca documentos no momento da query | Incorpora conhecimento nos pesos do modelo |
| Latência | Maior (busca + contexto longo) | Menor (sem busca em runtime) |
| Custo por query | Mais tokens (contexto grande) | Menos tokens |
| Atualização de conhecimento | Imediato (só reindexar) | Requer novo fine-tune |
| Melhor para | FAQs dinâmicas, documentos que mudam | Tom, estilo, domínio fixo |

**Estratégia ideal: RAG + Fine-tuning juntos.**
- Fine-tuning ensina o modelo o *estilo* e o *domínio* (ex: linguagem jurídica, termos técnicos do setor)
- RAG fornece os *fatos específicos* em tempo real

---

## Flywheel de dados

```
Tenant usa a plataforma
  → Atendimentos geram pares (pergunta do usuário, resposta do agente)
  → Sistema coleta automaticamente no dataset (pendente de aprovação)
  → Curador humano aprova/edita os pares
  → Dataset cresce com o uso
  → Fine-tune gera modelo cada vez mais alinhado ao domínio
  → Modelo melhor → melhores respostas → mais atendimentos resolvidos
```

---

## Schema — Novas Tabelas

### `dataset_treinamento`

```python
class DatasetTreinamento(Base):
    __tablename__ = "dataset_treinamento"

    id: int (PK)
    tenant_id: int (FK → tenant)
    instrucao: str (TEXT)       # a pergunta / tarefa
    entrada: str | None (TEXT)  # contexto adicional (ex: trecho do documento)
    saida: str (TEXT)           # resposta esperada (ground truth)
    fonte: FonteDataset         # atendimento | conversa | manual
    fonte_id: int | None        # ID do atendimento ou conversa de origem
    aprovado: bool = False      # curadoria humana obrigatória antes de usar
    created_at: datetime
    atualizado_em: datetime

class FonteDataset(str, Enum):
    ATENDIMENTO = "atendimento"
    CONVERSA = "conversa"
    MANUAL = "manual"
```

### `fine_tune_job`

```python
class FineTuneJob(Base):
    __tablename__ = "fine_tune_job"

    id: int (PK)
    tenant_id: int (FK → tenant)
    modelo_base: str            # ex: "qwen2.5:7b"
    modelo_saida: str           # ex: "minha-empresa-juridico-v1"
    status: FineTuneStatus
    dataset_size: int           # quantos exemplos aprovados foram usados
    hiperparametros: dict (JSON)
        # epochs, learning_rate, lora_rank, lora_alpha, max_seq_length
    log_saida: str | None (TEXT)  # output do processo (streaming via SSE)
    erro: str | None            # mensagem de erro se status=ERRO
    iniciado_em: datetime | None
    concluido_em: datetime | None
    created_at: datetime

class FineTuneStatus(str, Enum):
    PENDENTE = "pendente"
    RODANDO = "rodando"
    CONCLUIDO = "concluido"
    ERRO = "erro"
    CANCELADO = "cancelado"
```

---

## Coleta Automática de Dados

### De atendimentos (WhatsApp/Telegram)

Ao encerrar um atendimento (`status → ENCERRADO`), extrair pares do histórico:

```python
async def coletar_de_atendimento(atendimento_id: int, db: AsyncSession) -> int:
    mensagens = await MensagemAtendimentoService.listar(atendimento_id, db)

    pares_coletados = 0
    # Percorre mensagens agrupando: CONTATO pergunta → AGENTE responde
    for i, msg in enumerate(mensagens):
        if msg.origem == "CONTATO":
            # Procura próxima resposta do AGENTE
            resposta = next(
                (m for m in mensagens[i+1:] if m.origem == "AGENTE"),
                None
            )
            if resposta:
                await DatasetService.criar(DatasetCreate(
                    tenant_id=...,
                    instrucao=msg.conteudo,
                    saida=resposta.conteudo,
                    fonte=FonteDataset.ATENDIMENTO,
                    fonte_id=atendimento_id,
                    aprovado=False  # sempre começa não aprovado
                ))
                pares_coletados += 1

    return pares_coletados
```

### De conversas (chat web)

Similar, mas filtrando `role=user` → `role=assistant`.

---

## DatasetService

```python
class DatasetService:
    async def criar(item: DatasetCreate, db) -> DatasetTreinamento
    async def listar(tenant_id: int, aprovado: bool | None, fonte: FonteDataset | None, db) -> list
    async def aprovar(item_id: int, tenant_id: int, db) -> DatasetTreinamento
    async def reprovar(item_id: int, tenant_id: int, db) -> DatasetTreinamento
    async def atualizar(item_id: int, data: DatasetUpdate, tenant_id: int, db) -> DatasetTreinamento
    async def deletar(item_id: int, tenant_id: int, db) -> None
    async def exportar_jsonl(tenant_id: int, db) -> str:
        # Retorna string JSONL com todos os pares aprovados
        # Formato Alpaca: {"instruction": ..., "input": ..., "output": ...}
    async def coletar_de_atendimento(atendimento_id: int, db) -> int
    async def coletar_de_conversa(conversa_id: int, db) -> int
```

---

## Fine-Tuning com Unsloth

[Unsloth](https://github.com/unslothai/unsloth) é uma biblioteca que implementa LoRA/QLoRA de forma eficiente para CPU e GPU. Permite fine-tuning de modelos como Qwen, Llama e Mistral com menos de 8GB de RAM.

### FineTuneService

```python
class FineTuneService:

    async def iniciar(job: FineTuneJob, db: AsyncSession) -> None:
        # Atualiza status → RODANDO
        # Exporta dataset aprovado como arquivo JSONL temporário
        # Roda _executar_treino em background (ThreadPoolExecutor)

    def _executar_treino(job: FineTuneJob, dataset_path: str) -> None:
        """Roda em thread separada (bloqueia por horas)"""
        from unsloth import FastLanguageModel

        # 1. Carrega modelo base com LoRA
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=job.modelo_base,
            max_seq_length=job.hiperparametros.get("max_seq_length", 2048),
            load_in_4bit=True,  # QLoRA — economiza VRAM/RAM
        )
        model = FastLanguageModel.get_peft_model(
            model,
            r=job.hiperparametros.get("lora_rank", 16),
            lora_alpha=job.hiperparametros.get("lora_alpha", 16),
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        )

        # 2. Prepara dataset
        dataset = load_dataset("json", data_files=dataset_path)

        # 3. Treina com SFTTrainer (HuggingFace trl)
        trainer = SFTTrainer(
            model=model,
            tokenizer=tokenizer,
            train_dataset=dataset["train"],
            max_seq_length=2048,
            args=TrainingArguments(
                output_dir=f"/tmp/finetuned/{job.modelo_saida}",
                num_train_epochs=job.hiperparametros.get("epochs", 3),
                learning_rate=job.hiperparametros.get("learning_rate", 2e-4),
                per_device_train_batch_size=2,
                gradient_accumulation_steps=4,
            ),
        )
        trainer.train()

        # 4. Exporta para GGUF (formato Ollama)
        model.save_pretrained_gguf(
            f"/tmp/gguf/{job.modelo_saida}",
            tokenizer,
            quantization_method="q4_k_m"
        )

        # 5. Registra no Ollama via API
        _registrar_no_ollama(job.modelo_saida)

    def _registrar_no_ollama(modelo_saida: str) -> None:
        # Cria Modelfile: FROM /tmp/gguf/{modelo_saida}/model.gguf
        # POST http://ollama:11434/api/create com o Modelfile
        # Ollama disponibiliza o modelo via API normalmente
```

### Hiperparâmetros padrão

```python
HIPERPARAMETROS_PADRAO = {
    "epochs": 3,
    "learning_rate": 2e-4,
    "lora_rank": 16,
    "lora_alpha": 16,
    "max_seq_length": 2048,
}
```

---

## Endpoints

```
# Dataset
GET    /api/fine-tuning/dataset
    → Lista pares (filtros: aprovado, fonte, page)

POST   /api/fine-tuning/dataset
    → Cria par manual (instrucao, entrada, saida)

PUT    /api/fine-tuning/dataset/{id}
    → Edita par (instrucao, entrada, saida)

POST   /api/fine-tuning/dataset/{id}/aprovar
    → aprovado = True

POST   /api/fine-tuning/dataset/{id}/reprovar
    → aprovado = False

DELETE /api/fine-tuning/dataset/{id}
    → Remove par

POST   /api/fine-tuning/dataset/coletar-atendimentos
    → Coleta pares de todos atendimentos ENCERRADOS não coletados ainda

GET    /api/fine-tuning/dataset/exportar
    → Download do arquivo .jsonl com todos pares aprovados

# Jobs
GET    /api/fine-tuning/jobs
    → Lista jobs do tenant

POST   /api/fine-tuning/jobs
    → Inicia novo job (modelo_base, modelo_saida, hiperparametros)

GET    /api/fine-tuning/jobs/{id}
    → Status + progresso + hiperparametros

GET    /api/fine-tuning/jobs/{id}/log
    → SSE: stream do log de treino em tempo real

POST   /api/fine-tuning/jobs/{id}/cancelar
    → Cancela job em andamento
```

---

## SSE do log de treino

Durante o treino, o `_executar_treino` escreve o output progressivamente. O endpoint `/log` faz SSE:

```python
@router.get("/jobs/{job_id}/log")
async def stream_log(job_id: int, ...):
    async def gerador():
        ultimo_pos = 0
        while True:
            job = await FineTuneJobService.get_by_id(job_id, db)
            if job.log_saida:
                novo = job.log_saida[ultimo_pos:]
                if novo:
                    yield f"data: {json.dumps({'log': novo})}\n\n"
                    ultimo_pos = len(job.log_saida)
            if job.status in (FineTuneStatus.CONCLUIDO, FineTuneStatus.ERRO):
                yield f"data: {json.dumps({'status': job.status})}\n\n"
                break
            await asyncio.sleep(2)
    return StreamingResponse(gerador(), media_type="text/event-stream")
```

---

## Uso do modelo fine-tunado

Após conclusão do job, `modelo_saida` fica disponível no Ollama local. O tenant pode configurar qualquer agente para usá-lo:

```
SettingsView.vue → Config LLM do tenant:
  Provider: [Ollama (local) ▼]
  Modelo:   [minha-empresa-juridico-v1 ▼]   ← aparece na lista de modelos Ollama
```

O `get_tenant_llm()` já busca o modelo configurado — nenhuma mudança extra necessária.

---

## Frontend — `/fine-tuning`

### DatasetView.vue

```
┌──────────────────────────────────────────────────────────┐
│ Dataset de Treinamento                [+ Adicionar manual]│
│                                                          │
│ Filtros: [Todos ▼] [Atendimento ▼]  [Coletar novos]     │
│                                                          │
│ ┌─────────────────────────────────────────────────────┐  │
│ │ ✗  Qual é o prazo para rescisão?   [ATENDIMENTO]   │  │
│ │    "O prazo padrão é de 30 dias..."  [Editar][✓][✗]│  │
│ ├─────────────────────────────────────────────────────┤  │
│ │ ✓  Como calcular multa rescisória? [MANUAL]        │  │
│ │    "A multa é calculada sobre..."   [Editar][✗]    │  │
│ └─────────────────────────────────────────────────────┘  │
│                                    [Exportar JSONL]      │
└──────────────────────────────────────────────────────────┘
```

### FineTuningJobsView.vue

```
┌──────────────────────────────────────────────────────────┐
│ Fine-Tuning Jobs                    [+ Novo Treinamento] │
│                                                          │
│ ┌──────────────────────────────────────────────────────┐ │
│ │ juridico-v2          CONCLUÍDO     847 exemplos      │ │
│ │ Base: qwen2.5:7b     3 épocas      2h 14min          │ │
│ │ [Ver log] [Usar este modelo]                         │ │
│ ├──────────────────────────────────────────────────────┤ │
│ │ juridico-v3          RODANDO ████████░░ 73%          │ │
│ │ Base: qwen2.5:7b     Época 2/3     1h 03min decor.   │ │
│ │ [Ver log ao vivo] [Cancelar]                         │ │
│ └──────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

Modal "Novo Treinamento":
- Dropdown de modelo base (lista modelos disponíveis no Ollama)
- Campo nome do modelo de saída
- Sliders de hiperparâmetros (com tooltip explicando cada um)
- Preview: "X pares aprovados disponíveis"

---

## Dependências

```toml
dependencies = [
    "unsloth>=2024.12.0",     # fine-tuning eficiente LoRA/QLoRA
    "trl>=0.12.0",             # SFTTrainer (HuggingFace)
    "datasets>=3.0.0",         # load_dataset JSONL
    "transformers>=4.47.0",    # base HuggingFace
    "torch>=2.1.0",            # PyTorch (CPU ou CUDA)
]
```

**Nota:** Unsloth requer PyTorch. Em CPU o treino é mais lento (~10x) mas funciona. Com GPU (CUDA) é viável em horas.

---

## Testes

```
tests/test_finetuning/
├── conftest.py
├── test_dataset_service.py
│   ├── test_criar_par_manual
│   ├── test_aprovar_reprovar
│   ├── test_exportar_jsonl_formato_alpaca
│   ├── test_coletar_de_atendimento
│   ├── test_apenas_aprovados_no_export
│   └── test_isolamento_tenant
├── test_finetuning_router.py
│   ├── test_listar_dataset
│   ├── test_criar_par
│   ├── test_iniciar_job
│   ├── test_status_job
│   └── test_cancelar_job
└── test_finetuning_service.py
    ├── test_iniciar_muda_status_para_rodando    — mock _executar_treino
    ├── test_concluido_registra_no_ollama        — mock Ollama API
    └── test_erro_atualiza_campo_erro
```

---

## Ordem de Implementação

```
1.  Branch: fase-20
2.  Alembic: tabelas dataset_treinamento + fine_tune_job
3.  fine_tuning/models.py + schemas.py
4.  🔴 RED: test_dataset_service.py
5.  🟢 GREEN: fine_tuning/dataset_service.py
6.  🔴 RED: test_finetuning_router.py
7.  🟢 GREEN: fine_tuning/router.py (dataset endpoints)
8.  🔴 RED: test_finetuning_service.py
9.  🟢 GREEN: fine_tuning/job_service.py (FineTuneService com mock treino)
10. fine_tuning/router.py (job endpoints + SSE log)
11. Integração: coletar de atendimento ao encerrar
12. Integração: coletar de conversa ao arquivar
13. Frontend: DatasetView.vue + FineTuningJobsView.vue
14. Docker: adicionar torch + unsloth (ou imagem separada)
```

---

## Gotchas

- **Treino bloqueia:** rodar em `ThreadPoolExecutor` ou container/worker separado. Nunca no event loop principal.
- **RAM:** modelo base `qwen2.5:7b` em 4bit usa ~5GB. Certificar que o servidor tem pelo menos 8GB disponíveis durante o treino.
- **Unsloth em produção:** considerar um container dedicado `trainer` sem GPU inicialmente — treino lento mas funcional. Migrar para GPU conforme crescer.
- **Formato GGUF → Ollama:** Ollama só aceita modelos no formato GGUF via Modelfile. Exportar com `save_pretrained_gguf` com quantização q4_k_m.
- **Modelos custom na lista:** ao listar modelos Ollama (`GET /ollama/models`), modelos fine-tunados aparecem normalmente — sem mudança na UI de seleção de modelo.
- **Dados de curadoria:** pares não aprovados NUNCA entram no treino. Criar validação no `exportar_jsonl` e `iniciar_job`.
