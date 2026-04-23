"""
Azure gpt-image-2 text-to-image test script (via LLM proxy).

Mirrors chat-completion-http-post.py style. Sends a JSON request to
the /images/generations endpoint and saves the generated PNG locally.

Usage:
    python image-generation-http-post.py                # Normal output
    python image-generation-http-post.py --full          # Include full JSON response (truncated b64)
    python image-generation-http-post.py --prompt "..."  # Custom prompt
"""

import base64
import json
import os
import sys
import time
from datetime import datetime

import requests

# ============================================================
# Configuration
# ============================================================
DEV_IP = "11.154.216.99"
DEV_HOST = "apidev.gameai-llm.woa.com"
REL_IP = "11.154.216.130"
REL_HOST = "api.gameai-llm.woa.com"
HOST = REL_HOST
TOKEN = "vMOLhJPrI4i9yG7NspmqAV5tdk1EonxX"
ENDPOINT = f"http://{HOST}/llm-service/azure/public"

# gpt-image-2 requires api-version >= 2025-04-01-preview
DEPLOYMENT_ID = "gpt-image-2"
API_VERSION = "2025-04-01-preview"

# Output dir for generated images (auto-created)
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "img")

# ============================================================
# Request
# ============================================================
URL = (
    f"{ENDPOINT}/openai/deployments/{DEPLOYMENT_ID}"
    f"/images/generations?api-version={API_VERSION}"
)

HEADERS = {
    "Content-Type": "application/json",
    "api-key": TOKEN,
}

# Default prompt; override with --prompt "..."
DEFAULT_PROMPT = "A cute red panda eating bamboo, photorealistic"

PAYLOAD_BASE = {
    "model": DEPLOYMENT_ID,
    "prompt": DEFAULT_PROMPT,
    "size": "1024x1024",
    "n": 1,
    "output_format": "png",
    "quality": "medium",
}


# ============================================================
# Helpers
# ============================================================
def _parse_prompt_from_argv() -> str:
    """Pick up the value that follows --prompt, if provided."""
    if "--prompt" in sys.argv:
        idx = sys.argv.index("--prompt")
        if idx + 1 < len(sys.argv):
            return sys.argv[idx + 1]
    return DEFAULT_PROMPT


def _save_b64_image(b64: str, index: int) -> str:
    """Decode base64 PNG and save it under OUTPUT_DIR. Returns file path."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    fname = f"gpt-image-2-{ts}-{index}.png"
    path = os.path.join(OUTPUT_DIR, fname)
    with open(path, "wb") as f:
        f.write(base64.b64decode(b64))
    return path


def _truncate_b64_in_response(res: dict) -> dict:
    """Shallow-copy the response and truncate b64 payloads for readable dumps."""
    copy = {**res}
    data = copy.get("data")
    if isinstance(data, list):
        new_data = []
        for item in data:
            if isinstance(item, dict) and "b64_json" in item:
                b64 = item["b64_json"] or ""
                new_data.append(
                    {**item, "b64_json": f"<{len(b64)} bytes base64, truncated>"}
                )
            else:
                new_data.append(item)
        copy["data"] = new_data
    return copy


# ============================================================
# Send & Display
# ============================================================
def main() -> None:
    show_full = "--full" in sys.argv

    payload = {**PAYLOAD_BASE, "prompt": _parse_prompt_from_argv()}

    print("=" * 60)
    print(f"  Model:    {DEPLOYMENT_ID}")
    print(f"  Endpoint: {URL[:80]}...")
    print(f"  Prompt:   {payload['prompt']}")
    print(f"  Size:     {payload['size']}  Quality: {payload['quality']}  n={payload['n']}")
    print("=" * 60)

    start = time.time()
    try:
        response = requests.post(URL, headers=HEADERS, json=payload, timeout=600)
    except requests.ConnectionError as e:
        print(f"\n❌ 连接失败: {e}")
        sys.exit(1)
    except requests.Timeout:
        print("\n❌ 请求超时（当前设置 600s；高画质大尺寸图可能需要 1-3 分钟）")
        sys.exit(1)

    elapsed = time.time() - start

    # Status line
    status = response.status_code
    status_icon = "✅" if response.ok else "❌"
    print(f"\n{status_icon} HTTP {status}  ({elapsed:.2f}s)")
    print("-" * 60)

    # Parse response
    try:
        res = response.json()
    except json.JSONDecodeError:
        print(response.text)
        sys.exit(1)

    # Error response
    if not response.ok:
        print(f"错误信息: {json.dumps(res, indent=2, ensure_ascii=False)}")
        sys.exit(1)

    # Success: save images and show usage
    data = res.get("data", [])
    saved_paths = []
    for i, item in enumerate(data):
        b64 = item.get("b64_json")
        if b64:
            path = _save_b64_image(b64, i)
            saved_paths.append(path)
            print(f"[image {i}] saved → {path}")

    # Usage (three-dimensional for gpt-image-*)
    usage = res.get("usage", {})
    if usage:
        details = usage.get("input_tokens_details") or {}
        print("-" * 60)
        print(
            f"  Input:   total={usage.get('input_tokens', '?')}"
            f"  text={details.get('text_tokens', '?')}"
            f"  image={details.get('image_tokens', '?')}"
        )
        print(f"  Output:  {usage.get('output_tokens', '?')} (generated image tokens)")
        print(f"  Total:   {usage.get('total_tokens', '?')}")

        # Rough cost estimate (per the 5/8/30 USD per 1M tokens pricing)
        text_in = details.get("text_tokens") or 0
        image_in = details.get("image_tokens") or 0
        image_out = usage.get("output_tokens") or 0
        cost = (text_in * 0.005 + image_in * 0.008 + image_out * 0.030) / 1000.0
        print(f"  Est. cost: ${cost:.6f}")

        # Dump the raw usage object verbatim so we can see EVERY field the
        # upstream actually returns (including any nested details /
        # future-proof fields like output_tokens_details, cached tokens, etc.)
        print("-" * 60)
        print("  🔍 RAW usage object (verbatim):")
        print(json.dumps(usage, indent=4, ensure_ascii=False))

    # Model / size metadata
    model = res.get("model", "") or DEPLOYMENT_ID
    size = res.get("size", "")
    fmt = res.get("output_format", "")
    quality = res.get("quality", "")
    print(f"  Model:   {model}")
    if size or fmt or quality:
        print(f"  Output:  size={size}  format={fmt}  quality={quality}")

    print("=" * 60)

    # Optionally dump full response (with truncated b64)
    if show_full:
        print("\n[Full Response — b64 truncated]")
        print(json.dumps(_truncate_b64_in_response(res), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
