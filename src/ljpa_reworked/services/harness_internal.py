import sys
import asyncio
import logging

# Configure logging to go to stderr so it doesn't pollute stdout output
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

async def main():
    from google.antigravity import Agent, CapabilitiesConfig, LocalAgentConfig
    
    prompt = sys.stdin.read().strip()
    if not prompt:
        logger.error("No prompt provided via stdin.")
        sys.exit(1)
        
    logger.info("Initializing Agent via google.antigravity Python SDK inside container...")
    config = LocalAgentConfig(
        system_instructions="You are Harness 1 LinkedIn Post Vacancy Discovery Agent.",
        capabilities=CapabilitiesConfig(),
    )
    tokens = []
    async with Agent(config) as agent:
        resp = await agent.chat(prompt)
        async for token in resp:
            tokens.append(token)
            
    # Print the final result strictly to stdout
    print("".join(tokens), file=sys.stdout)

if __name__ == "__main__":
    asyncio.run(main())
