"""Language model served by agentgateway, attributed to the end user, agent and conversation.

Connect its "Language Model" output to an Agent's model input. Every model call goes to the gateway's
services listener (OpenAI-compatible) with:
  Authorization: Bearer <runtime gateway key>     (OPENAI_API_KEY of this Langflow instance)
  x-end-user-id     the serving end user (Langflow's LANGFLOW_SERVING_END_USER_HEADER identity)
  x-agent-slug      the catalog slug of the agent
  x-agui-thread-id  the conversation (AG-UI threadId = Langflow session, without the end-user scope prefix)
so the gateway's Logs/Analytics show usage per user and per agent. Outside a served run (Builder
playground) there is no end user and only the agent header is sent.
"""

import os

from langchain_openai import ChatOpenAI

from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.io import FloatInput, SecretStrInput, StrInput

SCOPE_SEPARATOR = "::"  # Langflow scopes served sessions as "<end user>::<session>"


class AgentGatewayModelComponent(LCModelComponent):
    display_name = "agentgateway Model"
    description = "Chat model via agentgateway (OpenAI-compatible), with end-user, agent and thread attribution."
    icon = "Network"
    name = "AgentGatewayModel"

    inputs = [
        *LCModelComponent._base_inputs,
        StrInput(name="model_name", display_name="Model", value="ollama/qwen3:8b",
                 info="A model name configured in the gateway (admin UI → LLM → Models), e.g. ollama/qwen3:8b."),
        StrInput(name="agent_slug", display_name="Agent slug", value="",
                 info="Catalog slug (slug in agent.yaml). Sent as x-agent-slug; defaults to the flow name."),
        FloatInput(name="temperature", display_name="Temperature", value=0.1, advanced=True),
        StrInput(name="base_url", display_name="Gateway URL", advanced=True,
                 value=os.getenv("OPENAI_BASE_URL", "http://agentgateway:4102/v1")),
        SecretStrInput(name="api_key", display_name="Gateway API key", advanced=True, required=False,
                       info="Leave empty to use this Langflow instance's OPENAI_API_KEY (its gateway key)."),
    ]

    def _attribution_headers(self) -> dict[str, str]:
        graph = getattr(self, "graph", None)
        end_user = getattr(graph, "end_user_id", None) if graph else None
        session = getattr(graph, "session_id", None) if graph else None
        if session and end_user and session.startswith(f"{end_user}{SCOPE_SEPARATOR}"):
            session = session[len(end_user) + len(SCOPE_SEPARATOR):]
        slug = self.agent_slug or (getattr(graph, "flow_name", None) if graph else None)
        headers = {"x-end-user-id": end_user, "x-agent-slug": slug, "x-agui-thread-id": session}
        return {k: str(v) for k, v in headers.items() if v}

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        api_key = self.api_key or os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            msg = "No gateway API key: set OPENAI_API_KEY for this Langflow instance or the component's API key."
            raise ValueError(msg)
        return ChatOpenAI(
            model=self.model_name,
            base_url=self.base_url,
            api_key=api_key,
            temperature=self.temperature,
            streaming=True,  # token streaming to the chat; the Agent decides how it consumes the stream
            default_headers=self._attribution_headers(),
        )
