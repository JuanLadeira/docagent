"""
Fase 6 — Router de agentes: lista os agentes disponíveis com suas skills.
"""
from fastapi import APIRouter

from docagent.schemas.chat import AgentInfo, SkillInfo
from docagent.agents.registry import AGENT_REGISTRY
from docagent.skills import SKILL_REGISTRY

router = APIRouter()


@router.get("/agents", response_model=list[AgentInfo])
def list_agents() -> list[AgentInfo]:
    """Lista todos os agentes disponíveis com suas skills e metadados."""
    result = []
    for config in AGENT_REGISTRY.values():
        skills = [
            SkillInfo(
                name=SKILL_REGISTRY[name].name,
                label=SKILL_REGISTRY[name].label,
                icon=SKILL_REGISTRY[name].icon,
                description=SKILL_REGISTRY[name].description,
            )
            for name in config.skill_names
            if name in SKILL_REGISTRY
        ]
        result.append(AgentInfo(
            id=config.id,
            name=config.name,
            description=config.description,
            skills=skills,
        ))
    return result
