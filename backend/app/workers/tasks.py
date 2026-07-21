import asyncio


async def sleep_and_log(ctx, message: str) -> str:
    """Throwaway M18 task: proves a job enqueued from one process is picked
    up and executed by the separate worker container, not the API process."""
    await asyncio.sleep(2)
    print(f"[arq task] {message}")
    return f"done: {message}"
