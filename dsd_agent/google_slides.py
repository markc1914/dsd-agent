"""Google Slides handler for DSD Agent."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .image_analyzer import (
    ArchitectureImageAnalyzer,
    ArchitectureAnalysis,
    SystemComponent,
)
from .pptx_handler import Placeholder, ArchitectureSlide

# Google API imports - optional dependency
try:
    from google.oauth2 import service_account
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False


SCOPES = ['https://www.googleapis.com/auth/presentations']


@dataclass
class MappingResult:
    """Result of mapping components to placeholders."""
    slide_index: int
    slide_title: str
    mappings: list[tuple[Placeholder, SystemComponent]]
    unmapped_placeholders: list[Placeholder]
    unmapped_components: list[SystemComponent]


class GoogleSlidesDocument:
    """Handler for Google Slides presentations."""

    def __init__(self, credentials_path: str | Path | None = None):
        if not GOOGLE_API_AVAILABLE:
            raise ImportError(
                "Google API libraries not installed. "
                "Install with: pip install google-api-python-client google-auth-oauthlib"
            )

        self.credentials_path = credentials_path
        self.service = None
        self.presentation_id: str | None = None
        self.presentation: dict | None = None
        self._architecture_slides: list[ArchitectureSlide] | None = None

    def _get_credentials(self) -> Credentials:
        """Get Google API credentials."""
        creds = None

        # Try service account first
        if self.credentials_path:
            creds_path = Path(self.credentials_path)
            if creds_path.exists():
                if 'service_account' in creds_path.read_text():
                    creds = service_account.Credentials.from_service_account_file(
                        str(creds_path), scopes=SCOPES
                    )
                else:
                    # OAuth2 credentials file
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(creds_path), SCOPES
                    )
                    creds = flow.run_local_server(port=0)

        if not creds:
            raise ValueError(
                "No valid credentials found. Provide a service account JSON file "
                "or OAuth2 credentials via --credentials or GOOGLE_APPLICATION_CREDENTIALS"
            )

        return creds

    def connect(self):
        """Connect to Google Slides API."""
        creds = self._get_credentials()
        self.service = build('slides', 'v1', credentials=creds)

    def load_presentation(self, presentation_id: str) -> dict:
        """Load a presentation by ID."""
        if not self.service:
            self.connect()

        self.presentation_id = presentation_id
        self.presentation = self.service.presentations().get(
            presentationId=presentation_id
        ).execute()

        return self.presentation

    @property
    def slide_count(self) -> int:
        if not self.presentation:
            return 0
        return len(self.presentation.get('slides', []))

    def _get_slide_title(self, slide: dict) -> str:
        """Extract the title from a slide."""
        for element in slide.get('pageElements', []):
            if 'shape' in element:
                shape = element['shape']
                if shape.get('placeholder', {}).get('type') == 'TITLE':
                    text_elements = shape.get('text', {}).get('textElements', [])
                    for te in text_elements:
                        if 'textRun' in te:
                            return te['textRun']['content'].strip()

        # Fallback: first text found
        for element in slide.get('pageElements', []):
            if 'shape' in element:
                text_elements = element['shape'].get('text', {}).get('textElements', [])
                for te in text_elements:
                    if 'textRun' in te:
                        text = te['textRun']['content'].strip()
                        if text and len(text) < 80:
                            return text

        return "Untitled"

    def _emu_to_inches(self, emu: dict) -> float:
        """Convert EMU dict to inches."""
        magnitude = emu.get('magnitude', 0)
        unit = emu.get('unit', 'EMU')
        if unit == 'EMU':
            return magnitude / 914400
        elif unit == 'PT':
            return magnitude / 72
        return magnitude

    def find_architecture_slides(self) -> list[ArchitectureSlide]:
        """Find all slides containing Lorem Ipsum placeholders."""
        if self._architecture_slides is not None:
            return self._architecture_slides

        if not self.presentation:
            return []

        architecture_slides = []

        for idx, slide in enumerate(self.presentation.get('slides', [])):
            title = self._get_slide_title(slide)
            placeholders = []

            for element in slide.get('pageElements', []):
                if 'shape' not in element:
                    continue

                shape = element['shape']
                text_elements = shape.get('text', {}).get('textElements', [])

                full_text = ""
                for te in text_elements:
                    if 'textRun' in te:
                        full_text += te['textRun']['content']

                if "lorem" in full_text.lower():
                    # Get position
                    transform = element.get('transform', {})
                    size = element.get('size', {})

                    left = transform.get('translateX', 0) / 914400
                    top = transform.get('translateY', 0) / 914400
                    width = size.get('width', {}).get('magnitude', 0) / 914400
                    height = size.get('height', {}).get('magnitude', 0) / 914400

                    ph = Placeholder(
                        slide_index=idx,
                        slide_title=title,
                        shape_name=element.get('objectId', ''),
                        text=full_text.strip(),
                        left=left,
                        top=top,
                        width=width,
                        height=height,
                        row_group=0
                    )
                    placeholders.append(ph)

            if placeholders:
                # Assign row groups
                placeholders = self._assign_row_groups(placeholders)
                placeholders.sort(key=lambda p: (p.row_group, p.left))

                architecture_slides.append(ArchitectureSlide(
                    index=idx,
                    title=title,
                    placeholders=placeholders
                ))

        self._architecture_slides = architecture_slides
        return architecture_slides

    def _assign_row_groups(self, placeholders: list[Placeholder]) -> list[Placeholder]:
        """Assign logical row groups based on vertical position."""
        if not placeholders:
            return placeholders

        sorted_ph = sorted(placeholders, key=lambda p: p.top)
        row_group = 0
        current_top = sorted_ph[0].top

        for ph in sorted_ph:
            if abs(ph.top - current_top) > 0.5:
                row_group += 1
                current_top = ph.top
            ph.row_group = row_group

        return placeholders

    def update_placeholder(self, slide_index: int, object_id: str, new_text: str) -> bool:
        """Update a specific placeholder with new text."""
        if not self.service or not self.presentation_id:
            return False

        requests = [
            {
                'deleteText': {
                    'objectId': object_id,
                    'textRange': {
                        'type': 'ALL'
                    }
                }
            },
            {
                'insertText': {
                    'objectId': object_id,
                    'insertionIndex': 0,
                    'text': new_text
                }
            }
        ]

        try:
            self.service.presentations().batchUpdate(
                presentationId=self.presentation_id,
                body={'requests': requests}
            ).execute()
            return True
        except Exception as e:
            print(f"Error updating {object_id}: {e}")
            return False

    def update_placeholders_batch(self, updates: dict[tuple[int, str], str]) -> int:
        """Update multiple placeholders at once."""
        if not self.service or not self.presentation_id:
            return 0

        requests = []
        for (slide_index, object_id), new_text in updates.items():
            requests.append({
                'deleteText': {
                    'objectId': object_id,
                    'textRange': {'type': 'ALL'}
                }
            })
            requests.append({
                'insertText': {
                    'objectId': object_id,
                    'insertionIndex': 0,
                    'text': new_text
                }
            })

        if not requests:
            return 0

        try:
            self.service.presentations().batchUpdate(
                presentationId=self.presentation_id,
                body={'requests': requests}
            ).execute()
            return len(updates)
        except Exception as e:
            print(f"Error in batch update: {e}")
            return 0

    def get_slide_summary(self) -> str:
        """Get a summary of architecture slides for display."""
        slides = self.find_architecture_slides()
        lines = [f"Found {len(slides)} slides with Lorem Ipsum placeholders:\n"]

        for slide in slides:
            lines.append(f"  Slide {slide.index + 1}: {slide.title}")
            lines.append(f"    - {len(slide.placeholders)} placeholders")

            rows = {}
            for ph in slide.placeholders:
                if ph.row_group not in rows:
                    rows[ph.row_group] = []
                rows[ph.row_group].append(ph)

            for row_num, phs in sorted(rows.items()):
                lines.append(f"    - Row {row_num + 1}: {len(phs)} boxes")

        return "\n".join(lines)


class GoogleSlidesAgent:
    """Agent for populating Google Slides with architecture data."""

    MAPPING_PROMPT = """You are an expert at mapping architecture components to presentation placeholders.

Given a list of system components extracted from an architecture source and a list of placeholders in a slide, create the best mapping between them.

SLIDE INFO:
Title: {slide_title}
Slide Type: {slide_type}

PLACEHOLDERS (in visual order, organized by rows):
{placeholders_info}

EXTRACTED COMPONENTS:
{components_info}

MAPPING RULES:
1. Match components to placeholders based on position and category
2. Top rows = presentation/channel layer, middle = application/integration, bottom = data/infrastructure
3. If there are more placeholders than components, use "TBD" for extras
4. For legend boxes (usually on the right side), use category names

Return your mapping as JSON:
{{
    "mappings": [
        {{
            "object_id": "exact object ID from placeholders",
            "component_name": "name to display",
            "confidence": "high|medium|low",
            "reasoning": "brief explanation"
        }}
    ]
}}

Return ONLY the JSON."""

    def __init__(self, api_key: str | None = None, credentials_path: str | Path | None = None):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
        self.image_analyzer = ArchitectureImageAnalyzer(api_key=api_key)
        self.document = GoogleSlidesDocument(credentials_path=credentials_path)

    def load_presentation(self, presentation_id: str) -> str:
        """Load a Google Slides presentation."""
        self.document.load_presentation(presentation_id)
        return self.document.get_slide_summary()

    def analyze_source(
        self,
        source_path: str | Path | None = None,
        notes: str | None = None,
        mermaid_code: str | None = None,
    ) -> ArchitectureAnalysis:
        """Analyze an architecture source."""
        if source_path:
            return self.image_analyzer.analyze_image(source_path)
        elif notes:
            return self.image_analyzer.analyze_text_notes(notes)
        elif mermaid_code:
            return self.image_analyzer.analyze_mermaid(mermaid_code)
        else:
            raise ValueError("Must provide source_path, notes, or mermaid_code")

    def _format_placeholders(self, placeholders: list[Placeholder]) -> str:
        """Format placeholders for the prompt."""
        lines = []
        current_row = -1

        for ph in placeholders:
            if ph.row_group != current_row:
                current_row = ph.row_group
                lines.append(f"\n  Row {current_row + 1}:")
            lines.append(f"    - {ph.shape_name}: position ({ph.left:.1f}, {ph.top:.1f})")

        return "\n".join(lines)

    def _format_components(self, components: list[SystemComponent]) -> str:
        """Format components for the prompt."""
        lines = []
        for i, comp in enumerate(components, 1):
            lines.append(
                f"  {i}. {comp.name}\n"
                f"     Category: {comp.category}\n"
                f"     Layer: {comp.layer or 'unspecified'}"
            )
        return "\n".join(lines)

    def _determine_slide_type(self, slide: ArchitectureSlide) -> str:
        """Determine the type of architecture slide."""
        title_lower = slide.title.lower()
        if "current" in title_lower:
            return "Current State Architecture"
        elif "target" in title_lower or "future" in title_lower:
            return "Target State Architecture"
        elif "timeline" in title_lower:
            return "Implementation Timeline"
        else:
            return "Architecture Diagram"

    def create_mapping(
        self,
        slide: ArchitectureSlide,
        analysis: ArchitectureAnalysis,
    ) -> MappingResult:
        """Create a mapping between components and placeholders."""
        prompt = self.MAPPING_PROMPT.format(
            slide_title=slide.title,
            slide_type=self._determine_slide_type(slide),
            placeholders_info=self._format_placeholders(slide.placeholders),
            components_info=self._format_components(analysis.components),
        )

        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text

        # Parse JSON
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
                raise ValueError(f"Could not parse mapping response")

        # Build mapping result
        mappings = []
        mapped_objects = set()
        mapped_components = set()

        ph_by_id = {ph.shape_name: ph for ph in slide.placeholders}
        comp_by_name = {c.name: c for c in analysis.components}

        for m in data.get("mappings", []):
            object_id = m.get("object_id")
            component_name = m.get("component_name")

            if object_id in ph_by_id:
                ph = ph_by_id[object_id]
                comp = comp_by_name.get(component_name)
                if comp is None:
                    comp = SystemComponent(
                        name=component_name,
                        category="unknown",
                        description=m.get("reasoning", ""),
                    )
                mappings.append((ph, comp))
                mapped_objects.add(object_id)
                if component_name in comp_by_name:
                    mapped_components.add(component_name)

        unmapped_ph = [ph for ph in slide.placeholders if ph.shape_name not in mapped_objects]
        unmapped_comp = [c for c in analysis.components if c.name not in mapped_components]

        return MappingResult(
            slide_index=slide.index,
            slide_title=slide.title,
            mappings=mappings,
            unmapped_placeholders=unmapped_ph,
            unmapped_components=unmapped_comp,
        )

    def apply_mapping(self, mapping_result: MappingResult) -> int:
        """Apply a mapping result to the presentation."""
        updates = {}
        for ph, comp in mapping_result.mappings:
            updates[(mapping_result.slide_index, ph.shape_name)] = comp.name

        return self.document.update_placeholders_batch(updates)

    def populate_slide(
        self,
        slide_index: int,
        analysis: ArchitectureAnalysis,
        dry_run: bool = False,
    ) -> MappingResult:
        """Populate a specific slide with architecture components."""
        slides = self.document.find_architecture_slides()
        target_slide = None
        for s in slides:
            if s.index == slide_index:
                target_slide = s
                break

        if target_slide is None:
            raise ValueError(f"Slide {slide_index + 1} not found or has no placeholders")

        mapping = self.create_mapping(target_slide, analysis)

        if not dry_run:
            self.apply_mapping(mapping)

        return mapping

    def populate_all_slides(
        self,
        analysis: ArchitectureAnalysis,
        slide_type_filter: str | None = None,
        dry_run: bool = False,
    ) -> list[MappingResult]:
        """Populate all architecture slides matching the filter."""
        slides = self.document.find_architecture_slides()
        results = []

        for slide in slides:
            slide_type = self._determine_slide_type(slide)

            if slide_type_filter and slide_type_filter.lower() not in slide_type.lower():
                continue

            mapping = self.create_mapping(slide, analysis)

            if not dry_run:
                self.apply_mapping(mapping)

            results.append(mapping)

        return results

    def get_mapping_summary(self, result: MappingResult) -> str:
        """Get a human-readable summary of a mapping result."""
        lines = [
            f"\nSlide {result.slide_index + 1}: {result.slide_title}",
            f"  Mapped {len(result.mappings)} placeholders:",
        ]

        for ph, comp in result.mappings:
            lines.append(f"    - '{comp.name}' -> {ph.shape_name[-15:]}")

        if result.unmapped_placeholders:
            lines.append(f"\n  {len(result.unmapped_placeholders)} unmapped placeholders")

        if result.unmapped_components:
            lines.append(f"  {len(result.unmapped_components)} unused components")

        return "\n".join(lines)
