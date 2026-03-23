from sqlalchemy import JSON, Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from docagent.database import Base


class McpServer(Base):
    __tablename__ = "mcp_server"

    nome: Mapped[str] = mapped_column(String(255))
    descricao: Mapped[str] = mapped_column(Text, default="")
    command: Mapped[str] = mapped_column(String(255))
    args: Mapped[list] = mapped_column(JSON, default=list)
    env: Mapped[dict] = mapped_column(JSON, default=dict)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    tools: Mapped[list["McpTool"]] = relationship(
        "McpTool", back_populates="server", cascade="all, delete-orphan"
    )


class McpTool(Base):
    __tablename__ = "mcp_tool"

    server_id: Mapped[int] = mapped_column(ForeignKey("mcp_server.id", ondelete="CASCADE"))
    tool_name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")

    server: Mapped["McpServer"] = relationship("McpServer", back_populates="tools")
