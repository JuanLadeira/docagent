"""
Router de agentes: lista os agentes ativos com suas skills.
Os agentes sao lidos do banco de dados.
"""
from fastapi import APIRouter

from docagent.agente.services import AgenteServiceDep
from docagent.schemas.chat import AgentInfo, SkillInfo
from docagent.skills import SKILL_REGISTRY

router = APIRouter()


@router.get("/agents", response_model=list[AgentInfo])
async def list_agents(service: AgenteServiceDep) -> list[AgentInfo]:
    """Lista todos os agentes ativos com suas skills."""
    agentes = await service.get_all(apenas_ativos=True)
    result = []
    for agente in agentes:
        skills = [
            SkillInfo(
                name=SKILL_REGISTRY[name].name,
                label=SKILL_REGISTRY[name].label,
                icon=SKILL_REGISTRY[name].icon,
                description=SKILL_REGISTRY[name].description,
            )
            for name in agente.skill_names
            if name in SKILL_REGISTRY
        ]
        result.append(AgentInfo(
            id=str(agente.id),
            name=agente.nome,
            description=agente.descricao,
            skills=skills,
        ))
    return result
