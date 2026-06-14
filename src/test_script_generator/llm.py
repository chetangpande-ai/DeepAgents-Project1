from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from test_script_generator.config import Settings


def build_mesh_llm(settings: Settings) -> ChatOpenAI:
    if not settings.mesh_api_key:
        raise ValueError("MESH_API_KEY is required to create the Mesh API LLM client.")
    if not settings.mesh_api_url:
        raise ValueError("MESH_API_URL is required to create the Mesh API LLM client.")
    if not settings.mesh_model:
        raise ValueError("MESH_MODEL is required to create the Mesh API LLM client.")

    return ChatOpenAI(
        api_key=SecretStr(settings.mesh_api_key),
        base_url=settings.mesh_api_url,
        model=settings.mesh_model,
        temperature=settings.tsg_temperature,
    )
