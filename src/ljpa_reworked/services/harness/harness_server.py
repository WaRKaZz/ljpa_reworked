# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fastapi",
#     "uvicorn",
#     "pydantic"
# ]
# ///

import logging
import subprocess
from collections.abc import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Antigravity Harness Runner API")


class HarnessRequest(BaseModel):
    prompt_file: str = "/app/prompts/harness_scraper.md"
    timeout: str = "8h"


async def agy_stream_generator(cmd: list[str]) -> AsyncGenerator[str, None]:
    logger.info(f"Running command: {' '.join(cmd)}")
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )

    if process.stdout:
        for line in process.stdout:
            yield line

    process.wait()
    if process.returncode != 0:
        yield f'{{"status": "error", "message": "agy process exited with {process.returncode}"}}\n'
    else:
        yield '{"status": "success", "message": "agy process finished successfully"}\n'


@app.post("/run-harness")
async def run_harness(req: HarnessRequest):
    cmd = [
        "agy",
        "--dangerously-skip-permissions",
        "--print",
        f"/goal Execute the task defined in {req.prompt_file}",
        "--print-timeout",
        req.timeout,
        "--output-format",
        "stream-json",
    ]

    return StreamingResponse(
        agy_stream_generator(cmd), media_type="application/x-ndjson"
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
