"""ComfyUI health check for the director app."""

import aiohttp


async def check_health(comfyui_url):
    """Check whether ComfyUI answers ``GET {comfyui_url}/system_stats``.

    The request times out after 2 seconds in total, 1 second to connect.
    Returns the ``comfyui`` dict ``{"url", "reachable", "device", "message"}``:
    ``url`` is ``comfyui_url`` as given, ``device`` is the first device's name
    (or None), and ``message`` is None when reachable, else the error text.
    """
    result = {
        "url": comfyui_url,
        "reachable": False,
        "device": None,
        "message": f"Can't reach ComfyUI at {comfyui_url}. Start ComfyUI, then retry.",
    }
    timeout = aiohttp.ClientTimeout(total=2, sock_connect=1)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(comfyui_url.rstrip("/") + "/system_stats") as resp:
                if resp.status != 200:
                    return result
                data = await resp.json(content_type=None)
    except Exception:
        return result
    device = None
    try:
        device = data["devices"][0]["name"]
    except (KeyError, IndexError, TypeError):
        pass
    result["reachable"] = True
    result["device"] = device
    result["message"] = None
    return result
