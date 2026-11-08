"""Task 2: an ADK agent whose history is cleaned before every model call (quarantine, raw-call removal,
control-token neutralization). The ADK session itself is never modified."""
from google.adk.agents import LlmAgent

from slipguard.integrations.adk import guarded_lite_llm


def read_file(filepath: str) -> str:
    """Read a file from the workspace."""
    with open(filepath, encoding="utf-8") as f:
        return f.read()


agent = LlmAgent(
    name="coder",
    model=guarded_lite_llm("hosted_vllm/google/gemma-4-31b-it", api_base="http://127.0.0.1:8000/v1",
                           extra_body={"chat_template_kwargs": {"enable_thinking": False}}),
    instruction="You are a careful coding agent.",
    tools=[read_file],
)
# What the guard did on the last call: agent.model.llm_client.last_report
