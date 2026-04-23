import argparse
import base64
import os
import traceback
from typing import List, Optional

import requests


DEFAULT_MODEL = "gemini-3.1-flash-image-preview"
DEFAULT_BASE_URL = "http://21.214.128.212/llm-service/gcs/data_label/publishers/google/models"
DEFAULT_TOKEN = "vMOLhJPrI4i9yG7NspmqAV5tdk1EonxX"


class ImageGenerator:
    @staticmethod
    def encode_image(image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    @staticmethod
    def send_request(
        prompt: str,
        image_base64: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
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
    def generate_image(
        image_path: str,
        prompt: str,
        output_dir: str,
        output_name_prefix: str,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        token: Optional[str] = None,
    ) -> List[str]:
        image_base64 = ImageGenerator.encode_image(image_path)
        response = ImageGenerator.send_request(
            prompt=prompt,
            image_base64=image_base64,
            model=model,
            base_url=base_url,
            token=token,
        )
        response.raise_for_status()
        return ImageGenerator.parse_response(response, output_dir, output_name_prefix)

    @staticmethod
    def generate_from_text(
        prompt: str,
        output_dir: str,
        output_name_prefix: str,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        token: Optional[str] = None,
    ) -> List[str]:
        response = ImageGenerator.send_request(
            prompt=prompt,
            image_base64=None,
            model=model,
            base_url=base_url,
            token=token,
        )
        response.raise_for_status()
        return ImageGenerator.parse_response(response, output_dir, output_name_prefix)


def generate_images_with_remote_api(
    prompt: str,
    image_path: Optional[str] = None,
    output_dir: str = "./img",
    output_name_prefix: str = "generated_output",
    model: str = DEFAULT_MODEL,
    base_url: str = DEFAULT_BASE_URL,
    token: Optional[str] = None,
) -> List[str]:
    if image_path:
        return ImageGenerator.generate_image(
            image_path=image_path,
            prompt=prompt,
            output_dir=output_dir,
            output_name_prefix=output_name_prefix,
            model=model,
            base_url=base_url,
            token=token,
        )
    return ImageGenerator.generate_from_text(
        prompt=prompt,
        output_dir=output_dir,
        output_name_prefix=output_name_prefix,
        model=model,
        base_url=base_url,
        token=token,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Remote image generation client.")
    parser.add_argument(
        "--image-path",
        required=False,
        default=None,
        help="Optional input image path for image-to-image generation.",
    )
    parser.add_argument("--prompt", required=True, help="Prompt for generation.")
    parser.add_argument("--output-dir", default="./img", help="Output directory.")
    parser.add_argument(
        "--output-prefix", default="generated_output", help="Output file prefix."
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Remote model name.")
    parser.add_argument(
        "--base-url", default=DEFAULT_BASE_URL, help="Remote API base URL."
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Bearer token; if omitted will use REMOTE_IMAGE_API_TOKEN env var.",
    )
    args = parser.parse_args()

    paths = generate_images_with_remote_api(
        prompt=args.prompt,
        image_path=args.image_path,
        output_dir=args.output_dir,
        output_name_prefix=args.output_prefix,
        model=args.model,
        base_url=args.base_url,
        token=args.token,
    )
    print(f"\nSaved {len(paths)} image(s).")


if __name__ == "__main__":
    main()
