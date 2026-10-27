from agents import Agent, OpenAIChatCompletionsModel, Runner, set_tracing_disabled
from openai import AsyncOpenAI
from settings import settings
from agent import config

set_tracing_disabled(True)

client = AsyncOpenAI(api_key=settings.gemini_api_key, base_url=config.GEMINI_BASE_URL)

madadgar = Agent(
    name="Madadgar",
    instructions=config.INSTRUCTIONS,
    model=OpenAIChatCompletionsModel(model=config.MODEL, openai_client=client),
)

async def run(history: list[dict]) -> str:
    result = await Runner.run(madadgar, history)
    return result.final_output