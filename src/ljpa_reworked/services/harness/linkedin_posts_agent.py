import os
import sys
import asyncio
import logging

async def main():
    from google.antigravity import Agent, CapabilitiesConfig, LocalAgentConfig
    
    level = logging.DEBUG if "--verbose" in sys.argv else logging.INFO
    logging.basicConfig(level=level, stream=sys.stderr, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s', force=True)
    logger = logging.getLogger(__name__)

    prompt_file = "prompts/linkedin_posts_agent_prompt.md"
    if "--prompt-file" in sys.argv:
        idx = sys.argv.index("--prompt-file")
        if idx + 1 < len(sys.argv):
            prompt_file = sys.argv[idx + 1]

    if os.path.exists(prompt_file):
        with open(prompt_file, "r", encoding="utf-8") as f:
            prompt = f.read().strip()
    elif not sys.stdin.isatty():
        prompt = sys.stdin.read().strip()
    else:
        prompt = ""

    if not prompt:
        logger.error("No prompt available.")
        sys.exit(1)
        
    config = LocalAgentConfig(
        system_instructions="You are LinkedIn Post Vacancy Discovery Agent.",
        capabilities=CapabilitiesConfig(),
    )
    tokens = []
    async with Agent(config) as agent:
        resp = await agent.chat(prompt)
        async for token in resp:
            tokens.append(token)
            
    print("".join(tokens), file=sys.stdout)

run_linkedin_posts_agent = main

if __name__ == "__main__":
    asyncio.run(main())
