from langchain_core.tools import tool, BaseTool


class HumanHandoffSkill:
    name = "human_handoff"
    label = "Transferência Humana"
    icon = "🙋"
    description = "Detecta quando o usuário quer falar com uma pessoa e sinaliza para os operadores"

    def __init__(self, flag: dict):
        self._flag = flag

    def as_tool(self) -> BaseTool:
        flag = self._flag

        @tool
        def solicitar_atendimento_humano(motivo: str = "") -> str:
            """Use esta ferramenta para sinalizar que um atendente humano precisa assumir o atendimento.
            Casos de uso:
            1. O usuário pediu explicitamente para falar com uma pessoa ou atendente.
            2. O agente concluiu a coleta de um pedido e precisa que um humano o processe (ex: confirmar preços, finalizar venda).
            3. A situação está além da capacidade do agente e requer intervenção humana.
            Sempre chame esta ferramenta ao final de um pedido confirmado."""
            flag['requested'] = True
            return "Atendente notificado com sucesso."

        return solicitar_atendimento_humano
