from pydantic import BaseModel


class McpToolPublic(BaseModel):
    id: int
    server_id: int
    tool_name: str
    description: str

    model_config = {"from_attributes": True}


class McpServerCreate(BaseModel):
    nome: str
    descricao: str = ""
    command: str
    args: list[str] = []
    env: dict[str, str] = {}
    ativo: bool = True


class McpServerUpdate(BaseModel):
    nome: str | None = None
    descricao: str | None = None
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    ativo: bool | None = None


class McpServerPublic(BaseModel):
    id: int
    nome: str
    descricao: str
    command: str
    args: list[str]
    env: dict[str, str]
    ativo: bool
    tools: list[McpToolPublic] = []

    model_config = {"from_attributes": True}
