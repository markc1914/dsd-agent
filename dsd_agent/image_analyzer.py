"""Image analyzer using Claude's vision capabilities."""

import base64
import io
import json
from pathlib import Path
from dataclasses import dataclass

import anthropic
from PIL import Image


# Anthropic's maximum image size is 5MB (5,242,880 bytes)
# We use a slightly smaller target to account for base64 encoding overhead
MAX_IMAGE_BYTES = 4_500_000  # ~4.5MB to leave room for base64 overhead


@dataclass
class SystemComponent:
    """A system component extracted from an architecture diagram."""
    name: str
    category: str  # e.g., "channel", "integration", "core_banking", "data", "external"
    description: str = ""
    layer: str = ""  # e.g., "presentation", "application", "data", "infrastructure"


@dataclass
class ArchitectureAnalysis:
    """Result of analyzing an architecture image."""
    components: list[SystemComponent]
    layers: list[str]
    raw_analysis: str
    source_type: str  # "whiteboard", "diagram", "mermaid", "notes"


def compress_image(image_path: Path, max_bytes: int = MAX_IMAGE_BYTES) -> tuple[bytes, str]:
    """Compress an image to fit within size limits while preserving quality.

    Returns tuple of (image_bytes, media_type).
    """
    img = Image.open(image_path)

    # Convert RGBA to RGB if necessary (for JPEG compatibility)
    if img.mode in ('RGBA', 'LA', 'P'):
        # Create white background
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    # Start with high quality JPEG
    quality = 95

    # Progressively reduce quality and/or size until under limit
    while True:
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=quality, optimize=True)
        size = buffer.tell()

        if size <= max_bytes:
            buffer.seek(0)
            return buffer.read(), "image/jpeg"

        # Try reducing quality first
        if quality > 30:
            quality -= 10
            continue

        # If quality is already low, reduce dimensions
        width, height = img.size
        new_width = int(width * 0.8)
        new_height = int(height * 0.8)

        if new_width < 100 or new_height < 100:
            # Can't reduce further, return what we have
            buffer.seek(0)
            return buffer.read(), "image/jpeg"

        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        quality = 85  # Reset quality for resized image


def encode_image(image_path: str | Path) -> tuple[str, str]:
    """Encode an image to base64 and determine media type.

    Automatically compresses large images to fit within API limits.
    """
    path = Path(image_path)

    # Check file size first
    file_size = path.stat().st_size

    if file_size <= MAX_IMAGE_BYTES:
        # File is small enough, use original
        suffix = path.suffix.lower()
        media_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        media_type = media_types.get(suffix, "image/png")

        with open(path, "rb") as f:
            data = base64.standard_b64encode(f.read()).decode("utf-8")

        return data, media_type

    # File is too large, compress it
    image_bytes, media_type = compress_image(path)
    data = base64.standard_b64encode(image_bytes).decode("utf-8")

    return data, media_type


class ArchitectureImageAnalyzer:
    """Analyzes architecture images using Claude's vision."""

    ANALYSIS_PROMPT = """Analyze this architecture diagram/whiteboard image and extract all system components.

For each component you identify, provide:
1. The exact name/label visible in the image
2. Its category (one of: channel, integration, middleware, core_banking, data, external, infrastructure, security, monitoring)
3. A brief description of what it likely does
4. Its architectural layer if discernible (presentation, application, integration, data, infrastructure)

IMPORTANT:
- Extract the EXACT text/names visible in the image
- If text is hard to read, make your best interpretation
- Include ALL boxes, systems, and labeled components
- Preserve the original naming (don't normalize or standardize names)

Return your analysis as JSON with this structure:
{
    "source_type": "whiteboard|diagram|mermaid|notes",
    "layers_identified": ["list", "of", "layers"],
    "components": [
        {
            "name": "Exact System Name",
            "category": "category",
            "description": "Brief description",
            "layer": "layer name"
        }
    ],
    "layout_notes": "Any notes about the visual layout/organization"
}

Return ONLY the JSON, no other text."""

    def __init__(self, api_key: str | None = None):
        """Initialize with Anthropic API key."""
        self.client = anthropic.Anthropic(api_key=api_key)

    def analyze_image(self, image_path: str | Path) -> ArchitectureAnalysis:
        """Analyze an architecture image and extract components."""
        image_data, media_type = encode_image(image_path)

        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": self.ANALYSIS_PROMPT,
                        },
                    ],
                }
            ],
        )

        response_text = message.content[0].text

        # Parse JSON response
        try:
            # Handle potential markdown code blocks
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            data = json.loads(response_text.strip())
        except json.JSONDecodeError:
            # Fallback: try to extract any JSON-like content
            import re
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                data = json.loads(json_match.group())
            else:
                raise ValueError(f"Could not parse response as JSON: {response_text[:500]}")

        components = []
        for comp in data.get("components", []):
            components.append(SystemComponent(
                name=comp.get("name", "Unknown"),
                category=comp.get("category", "unknown"),
                description=comp.get("description", ""),
                layer=comp.get("layer", ""),
            ))

        return ArchitectureAnalysis(
            components=components,
            layers=data.get("layers_identified", []),
            raw_analysis=response_text,
            source_type=data.get("source_type", "diagram"),
        )

    def analyze_text_notes(self, notes: str) -> ArchitectureAnalysis:
        """Analyze text notes describing an architecture."""
        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": f"""Analyze these architecture notes and extract all system components mentioned.

NOTES:
{notes}

For each component mentioned, provide:
1. The exact name
2. Its category (one of: channel, integration, middleware, core_banking, data, external, infrastructure, security, monitoring)
3. A brief description
4. Its architectural layer if discernible

Return your analysis as JSON with this structure:
{{
    "source_type": "notes",
    "layers_identified": ["list", "of", "layers"],
    "components": [
        {{
            "name": "System Name",
            "category": "category",
            "description": "Brief description",
            "layer": "layer name"
        }}
    ]
}}

Return ONLY the JSON, no other text.""",
                }
            ],
        )

        response_text = message.content[0].text

        # Parse JSON response
        try:
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            data = json.loads(response_text.strip())
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                data = json.loads(json_match.group())
            else:
                raise ValueError(f"Could not parse response: {response_text[:500]}")

        components = []
        for comp in data.get("components", []):
            components.append(SystemComponent(
                name=comp.get("name", "Unknown"),
                category=comp.get("category", "unknown"),
                description=comp.get("description", ""),
                layer=comp.get("layer", ""),
            ))

        return ArchitectureAnalysis(
            components=components,
            layers=data.get("layers_identified", []),
            raw_analysis=response_text,
            source_type="notes",
        )

    def analyze_mermaid(self, mermaid_code: str) -> ArchitectureAnalysis:
        """Analyze a Mermaid diagram code and extract components."""
        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": f"""Analyze this Mermaid diagram code and extract all system components.

MERMAID CODE:
```mermaid
{mermaid_code}
```

For each component/node in the diagram, provide:
1. The exact name/label
2. Its category (one of: channel, integration, middleware, core_banking, data, external, infrastructure, security, monitoring)
3. A brief description
4. Its architectural layer if discernible from the diagram structure

Return your analysis as JSON with this structure:
{{
    "source_type": "mermaid",
    "layers_identified": ["list", "of", "layers"],
    "components": [
        {{
            "name": "System Name",
            "category": "category",
            "description": "Brief description",
            "layer": "layer name"
        }}
    ]
}}

Return ONLY the JSON, no other text.""",
                }
            ],
        )

        response_text = message.content[0].text

        try:
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            data = json.loads(response_text.strip())
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                data = json.loads(json_match.group())
            else:
                raise ValueError(f"Could not parse response: {response_text[:500]}")

        components = []
        for comp in data.get("components", []):
            components.append(SystemComponent(
                name=comp.get("name", "Unknown"),
                category=comp.get("category", "unknown"),
                description=comp.get("description", ""),
                layer=comp.get("layer", ""),
            ))

        return ArchitectureAnalysis(
            components=components,
            layers=data.get("layers_identified", []),
            raw_analysis=response_text,
            source_type="mermaid",
        )
