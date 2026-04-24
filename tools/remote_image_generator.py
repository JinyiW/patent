import argparse
import base64
import os
import traceback
from typing import List, Optional

import requests


# ============================================================
# Backend: GPT-Image-2 (Azure proxy) — default
# ============================================================
GPT_IMAGE_HOST = "api.gameai-llm.woa.com"
GPT_IMAGE_ENDPOINT = f"http://{GPT_IMAGE_HOST}/llm-service/azure/public"
GPT_IMAGE_MODEL = "gpt-image-2"
GPT_IMAGE_API_VERSION = "2025-04-01-preview"
GPT_IMAGE_QUALITY = "low"

# ============================================================
# Backend: Gemini (legacy fallback)
# ============================================================
GEMINI_MODEL = "gemini-3.1-flash-image-preview"
GEMINI_BASE_URL = "http://21.214.128.212/llm-service/gcs/data_label/publishers/google/models"

# Shared token
DEFAULT_TOKEN = "vMOLhJPrI4i9yG7NspmqAV5tdk1EonxX"

# Default backend
DEFAULT_BACKEND = "gpt-image-2"  # or "gemini"


# ============================================================
# GPT-Image-2 backend
# ============================================================
class GPTImageBackend:
    @staticmethod
    def generate(
        prompt: str,
        output_dir: str,
        output_name_prefix: str,
        token: Optional[str] = None,
        size: str = "1024x1024",
        quality: str = GPT_IMAGE_QUALITY,
        timeout_sec: int = 600,
    ) -> List[str]:
        if token is None:
            token = os.getenv("REMOTE_IMAGE_API_TOKEN", DEFAULT_TOKEN)

        url = (
            f"{GPT_IMAGE_ENDPOINT}/openai/deployments/{GPT_IMAGE_MODEL}"
            f"/images/generations?api-version={GPT_IMAGE_API_VERSION}"
        )
        headers = {
            "Content-Type": "application/json",
            "api-key": token,
        }
        payload = {
            "prompt": prompt,
            "size": size,
            "n": 1,
            "quality": quality,
        }

        response = requests.post(url, headers=headers, json=payload, timeout=timeout_sec)
        response.raise_for_status()
        res = response.json()

        saved_paths: List[str] = []
        data = res.get("data", [])
        os.makedirs(output_dir, exist_ok=True)
        for index, item in enumerate(data):
            b64 = item.get("b64_json")
            if b64:
                fname = f"{output_name_prefix}_{index}.png"
                path = os.path.join(output_dir, fname)
                with open(path, "wb") as f:
                    f.write(base64.b64decode(b64))
                saved_paths.append(path)
                print(f"\nImage successfully saved to {path}")

        if not saved_paths:
            print("\nNo image data found in the response to save.")

        usage = res.get("usage", {})
        if usage:
            print(f"  Tokens: input={usage.get('input_tokens', '?')}, "
                  f"output={usage.get('output_tokens', '?')}, "
                  f"total={usage.get('total_tokens', '?')}")

        return saved_paths


# ============================================================
# Gemini backend (legacy)
# ============================================================
class GeminiBackend:
    @staticmethod
    def encode_image(image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    @staticmethod
    def send_request(
        prompt: str,
        image_base64: Optional[str] = None,
        model: str = GEMINI_MODEL,
        base_url: str = GEMINI_BASE_URL,
        token: Optional[str] = None,
        timeout_sec: int = 120,
    ) -> requests.Response:
        if token is None:
            token = os.getenv("REMOTE_IMAGE_API_TOKEN", DEFAULT_TOKEN)

        url = f"{base_url}/{model}:streamGenerateContent"
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {token}",
        }
        parts = [{"text": prompt}]
        if image_base64:
            parts.append(
                {
                    "inlineData": {
                        "mimeType": "image/png",
                        "data": image_base64,
                    }
                }
            )

        body = {
            "system_instruction": {"parts": {"text": "You are a helpful assistant."}},
            "contents": [
                {
                    "role": "user",
                    "parts": parts,
                }
            ],
            "generationConfig": {
                "temperature": 1,
                "maxOutputTokens": 32768,
                "responseModalities": ["TEXT", "IMAGE"],
                "topP": 0.95,
            },
        }

        return requests.post(url=url, headers=headers, json=body, timeout=timeout_sec)

    @staticmethod
    def parse_response(
        response: requests.Response, output_dir: str, output_name_prefix: str
    ) -> List[str]:
        output_text = ""
        output_image_base64_list: List[str] = []
        saved_paths: List[str] = []

        try:
            resp_json = response.json()

            if not isinstance(resp_json, list):
                raise ValueError("Response JSON is not a list.")

            print(f"Received {len(resp_json)} stream chunk(s).")

            for stream_part in resp_json:
                candidates = stream_part.get("candidates", [])
                for candidate in candidates:
                    content = candidate.get("content", {})
                    for part in content.get("parts", []):
                        text = part.get("text")
                        if text:
                            output_text += text
                        inline_data = part.get("inlineData")
                        if inline_data and inline_data.get("data"):
                            output_image_base64_list.append(inline_data["data"])

            if output_image_base64_list:
                os.makedirs(output_dir, exist_ok=True)
                for index, output_image_base64 in enumerate(output_image_base64_list):
                    decoded_image_bytes = base64.b64decode(output_image_base64)
                    final_output_image_name = f"{output_name_prefix}_{index}.png"
                    final_output_image_path = os.path.join(
                        output_dir, final_output_image_name
                    )
                    with open(final_output_image_path, "wb") as f:
                        f.write(decoded_image_bytes)
                    saved_paths.append(final_output_image_path)
                    print(f"\nImage successfully saved to {final_output_image_path}")
            else:
                print("\nNo image data found in the response to save.")

            if output_text:
                print("\nGenerated Text:")
                print(output_text[:800] + ("..." if len(output_text) > 800 else ""))
        except Exception as ex:
            print(f"response: {response.text}")
            print(
                f"Failed to parse response. Error: {ex}, "
                f"\ntraceback: {traceback.format_exc()}"
            )

        return saved_paths

    @staticmethod
    def generate(
        prompt: str,
        output_dir: str,
        output_name_prefix: str,
        image_path: Optional[str] = None,
        token: Optional[str] = None,
    ) -> List[str]:
        image_base64 = None
        if image_path:
            image_base64 = GeminiBackend.encode_image(image_path)
        response = GeminiBackend.send_request(
            prompt=prompt, image_base64=image_base64, token=token,
        )
        response.raise_for_status()
        return GeminiBackend.parse_response(response, output_dir, output_name_prefix)


# ============================================================
# Unified API (drop-in replacement for old interface)
# ============================================================
def generate_images_with_remote_api(
    prompt: str,
    image_path: Optional[str] = None,
    output_dir: str = "./img",
    output_name_prefix: str = "generated_output",
    backend: str = DEFAULT_BACKEND,
    token: Optional[str] = None,
    # Legacy params (ignored for gpt-image-2, kept for Gemini compat)
    model: str = "",
    base_url: str = "",
) -> List[str]:
    """Generate images from text (or image+text for Gemini backend).

    Args:
        backend: "gpt-image-2" (default) or "gemini".
    """
    if backend == "gemini":
        return GeminiBackend.generate(
            prompt=prompt,
            output_dir=output_dir,
            output_name_prefix=output_name_prefix,
            image_path=image_path,
            token=token,
        )

    # Default: gpt-image-2
    if image_path:
        print("Warning: gpt-image-2 does not support image-to-image. Ignoring image_path.")
    return GPTImageBackend.generate(
        prompt=prompt,
        output_dir=output_dir,
        output_name_prefix=output_name_prefix,
        token=token,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Remote image generation client.")
    parser.add_argument(
        "--image-path",
        required=False,
        default=None,
        help="Optional input image path (Gemini backend only).",
    )
    parser.add_argument("--prompt", required=True, help="Prompt for generation.")
    parser.add_argument("--output-dir", default="./img", help="Output directory.")
    parser.add_argument(
        "--output-prefix", default="generated_output", help="Output file prefix."
    )
    parser.add_argument(
        "--backend",
        default=DEFAULT_BACKEND,
        choices=["gpt-image-2", "gemini"],
        help="Image generation backend (default: gpt-image-2).",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="API token; if omitted will use REMOTE_IMAGE_API_TOKEN env var.",
    )
    args = parser.parse_args()

    paths = generate_images_with_remote_api(
        prompt=args.prompt,
        image_path=args.image_path,
        output_dir=args.output_dir,
        output_name_prefix=args.output_prefix,
        backend=args.backend,
        token=args.token,
    )
    print(f"\nSaved {len(paths)} image(s).")


if __name__ == "__main__":
    main()
