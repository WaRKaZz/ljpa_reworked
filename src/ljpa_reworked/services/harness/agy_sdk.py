import os
import sys
import asyncio
import logging

async def main():
    from google.antigravity import Agent, CapabilitiesConfig, LocalAgentConfig
    
    level = logging.DEBUG if "--verbose" in sys.argv else logging.INFO
    # Force reconfigure logging
    logging.basicConfig(level=level, stream=sys.stderr, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s', force=True)
    logger = logging.getLogger(__name__)
    
    if "--verbose" in sys.argv:
        logging.getLogger("google.antigravity").setLevel(logging.DEBUG)

    prompt_file = None
    if "--prompt-file" in sys.argv:
        idx = sys.argv.index("--prompt-file")
        if idx + 1 < len(sys.argv):
            prompt_file = sys.argv[idx + 1]

    if prompt_file and os.path.exists(prompt_file):
        with open(prompt_file, "r", encoding="utf-8") as f:
            prompt = f.read().strip()
    elif os.path.exists("prompts/harness_1_linkedin_posts.md"):
        with open("prompts/harness_1_linkedin_posts.md", "r", encoding="utf-8") as f:
            prompt = f.read().strip()
    elif not sys.stdin.isatty():
        prompt = sys.stdin.read().strip()
    else:
        prompt = ""

    if not prompt:
        logger.error("No prompt provided via --prompt-file, prompts/harness_1_linkedin_posts.md, or stdin.")
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
