from typing import Protocol, runtime_checkable


@runtime_checkable
class JobSource(Protocol):
    async def buscar(self, perfil: dict) -> list[dict]:
        """Busca vagas compatíveis com o perfil do candidato.

        Retorna lista de dicts com as chaves:
            titulo, empresa, localizacao, descricao, requisitos,
            url, fonte (FonteVaga.value), raw_data (dict)

        NUNCA propaga exceções — retorna [] em caso de erro.
        """
        ...
