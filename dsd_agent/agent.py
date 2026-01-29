"""Main DSD Agent logic for mapping architecture components to placeholders."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anthropic

from .pptx_handler import DSDDocument, ArchitectureSlide, Placeholder
from .image_analyzer import (
    ArchitectureImageAnalyzer,
    ArchitectureAnalysis,
    SystemComponent,
)
from .integration_patterns import (
    IntegrationPatternAnalyzer,
    IntegrationAnalysis,
    IntegrationPattern,
    format_pattern_summary,
)


@dataclass
class MappingResult:
    """Result of mapping components to placeholders."""
    slide_index: int
    slide_title: str
    mappings: list[tuple[Placeholder, SystemComponent]]
    unmapped_placeholders: list[Placeholder]
    unmapped_components: list[SystemComponent]
    integration_patterns: list[IntegrationPattern] = field(default_factory=list)


class DSDAgent:
    """Agent for populating Digital Solutioning Documents with architecture data."""

    MAPPING_PROMPT = """You are an expert at mapping architecture components to PowerPoint placeholders.

Given a list of system components extracted from an architecture source and a list of placeholders in a PowerPoint slide, create the best mapping between them.

SLIDE INFO:
Title: {slide_title}
Slide Type: {slide_type}

PLACEHOLDERS (in visual order, organized by rows):
{placeholders_info}

EXTRACTED COMPONENTS:
{components_info}

MAPPING RULES:
1. Match components to placeholders based on:
   - Position (top rows = presentation/channel layer, middle = application/integration, bottom = data/infrastructure)
   - Category alignment (channels at top, integrations in middle, databases at bottom)
   - Number of placeholders in each row should roughly match number of components in that layer

2. If there are more placeholders than components, leave extras as "TBD" or suggest appropriate generic names
3. If there are more components than placeholders, prioritize the most important/core systems
4. For legend boxes (usually on the right side, small), use category names like "Channel", "Integration", "Core System", "Data"

Return your mapping as JSON:
{{
    "mappings": [
        {{
            "shape_name": "exact shape name from placeholders",
            "component_name": "name to display",
            "confidence": "high|medium|low",
            "reasoning": "brief explanation"
        }}
    ],
    "notes": "any important observations"
}}

Return ONLY the JSON, no other text."""

    def __init__(self, api_key: str | None = None):
        """Initialize the DSD Agent."""
        self.client = anthropic.Anthropic(api_key=api_key)
        self.image_analyzer = ArchitectureImageAnalyzer(api_key=api_key)
        self.pattern_analyzer = IntegrationPatternAnalyzer(api_key=api_key)
        self.document: DSDDocument | None = None
        self._last_integration_analysis: IntegrationAnalysis | None = None

    def load_document(self, pptx_path: str | Path) -> str:
        """Load a DSD PowerPoint document."""
        self.document = DSDDocument(pptx_path)
        return self.document.get_slide_summary()

    def analyze_source(
        self,
        source_path: str | Path | None = None,
        notes: str | None = None,
        mermaid_code: str | None = None,
        analyze_patterns: bool = False,
    ) -> ArchitectureAnalysis:
        """Analyze an architecture source (image, notes, or mermaid)."""
        if source_path:
            analysis = self.image_analyzer.analyze_image(source_path)
        elif notes:
            analysis = self.image_analyzer.analyze_text_notes(notes)
        elif mermaid_code:
            analysis = self.image_analyzer.analyze_mermaid(mermaid_code)
        else:
            raise ValueError("Must provide source_path, notes, or mermaid_code")

        # Optionally analyze integration patterns
        if analyze_patterns and analysis.components:
            self._last_integration_analysis = self.pattern_analyzer.analyze_components(
                analysis.components
            )

        return analysis

    def analyze_integration_patterns(
        self,
        analysis: ArchitectureAnalysis | None = None,
    ) -> IntegrationAnalysis:
        """Analyze integration patterns in the architecture components."""
        if analysis is None and self._last_integration_analysis is not None:
            return self._last_integration_analysis

        if analysis is None:
            raise ValueError("No architecture analysis provided")

        self._last_integration_analysis = self.pattern_analyzer.analyze_components(
            analysis.components
        )
        return self._last_integration_analysis

    def get_integration_summary(self) -> str:
        """Get a summary of detected integration patterns."""
        if self._last_integration_analysis is None:
            return "No integration analysis performed yet."
        return format_pattern_summary(self._last_integration_analysis)

    def get_pattern_recommendations(self) -> dict[str, Any]:
        """Get recommendations based on detected integration patterns."""
        if self._last_integration_analysis is None:
            return {"error": "No integration analysis performed yet."}
        return self.pattern_analyzer.get_pattern_recommendations(
            self._last_integration_analysis
        )

    def _format_placeholders(self, placeholders: list[Placeholder]) -> str:
        """Format placeholders for the prompt."""
        lines = []
        current_row = -1

        for ph in placeholders:
            if ph.row_group != current_row:
                current_row = ph.row_group
                lines.append(f"\n  Row {current_row + 1}:")

            lines.append(
                f"    - {ph.shape_name}: position ({ph.left:.1f}, {ph.top:.1f}), "
                f"size {ph.width:.1f}x{ph.height:.1f}"
            )

        return "\n".join(lines)

    def _format_components(self, components: list[SystemComponent]) -> str:
        """Format components for the prompt."""
        lines = []
        for i, comp in enumerate(components, 1):
            lines.append(
                f"  {i}. {comp.name}\n"
                f"     Category: {comp.category}\n"
                f"     Layer: {comp.layer or 'unspecified'}\n"
                f"     Description: {comp.description}"
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
        elif "north star" in title_lower or "vision" in title_lower:
            return "Vision/Goals"
        else:
            return "Architecture Diagram"

    def create_mapping(
        self,
        slide: ArchitectureSlide,
        analysis: ArchitectureAnalysis,
        include_patterns: bool = True,
    ) -> MappingResult:
        """Create a mapping between components and placeholders for a slide."""
        # Get integration pattern context if available
        pattern_context = ""
        detected_patterns = []

        if include_patterns and self._last_integration_analysis:
            patterns = self._last_integration_analysis.patterns
            if patterns:
                pattern_names = [f"{p.name} ({p.pattern_type.value})" for p in patterns[:5]]
                pattern_context = f"\n\nINTEGRATION PATTERNS DETECTED:\n" + "\n".join(
                    f"  - {p}" for p in pattern_names
                )
                pattern_context += f"\n  Primary: {self._last_integration_analysis.primary_pattern.value}"
                pattern_context += f"\n  Style: {self._last_integration_analysis.integration_style}"
                detected_patterns = patterns

        prompt = self.MAPPING_PROMPT.format(
            slide_title=slide.title,
            slide_type=self._determine_slide_type(slide),
            placeholders_info=self._format_placeholders(slide.placeholders),
            components_info=self._format_components(analysis.components) + pattern_context,
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
                raise ValueError(f"Could not parse mapping response: {response_text[:500]}")

        # Build mapping result
        mappings = []
        mapped_shapes = set()
        mapped_components = set()

        # Create lookup dicts
        ph_by_name = {ph.shape_name: ph for ph in slide.placeholders}
        comp_by_name = {c.name: c for c in analysis.components}

        for m in data.get("mappings", []):
            shape_name = m.get("shape_name")
            component_name = m.get("component_name")

            if shape_name in ph_by_name:
                ph = ph_by_name[shape_name]
                # Find or create component
                comp = comp_by_name.get(component_name)
                if comp is None:
                    comp = SystemComponent(
                        name=component_name,
                        category="unknown",
                        description=m.get("reasoning", ""),
                    )
                mappings.append((ph, comp))
                mapped_shapes.add(shape_name)
                if component_name in comp_by_name:
                    mapped_components.add(component_name)

        # Find unmapped items
        unmapped_ph = [ph for ph in slide.placeholders if ph.shape_name not in mapped_shapes]
        unmapped_comp = [c for c in analysis.components if c.name not in mapped_components]

        return MappingResult(
            slide_index=slide.index,
            slide_title=slide.title,
            mappings=mappings,
            unmapped_placeholders=unmapped_ph,
            unmapped_components=unmapped_comp,
            integration_patterns=detected_patterns,
        )

    def apply_mapping(self, mapping_result: MappingResult) -> int:
        """Apply a mapping result to the document."""
        if self.document is None:
            raise ValueError("No document loaded")

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
        if self.document is None:
            raise ValueError("No document loaded")

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
        if self.document is None:
            raise ValueError("No document loaded")

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

    def save_document(self, output_path: str | Path | None = None) -> Path:
        """Save the modified document."""
        if self.document is None:
            raise ValueError("No document loaded")
        return self.document.save(output_path)

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
            lines.append(f"  {len(result.unmapped_components)} unused components:")
            for comp in result.unmapped_components[:5]:
                lines.append(f"    - {comp.name}")
            if len(result.unmapped_components) > 5:
                lines.append(f"    ... and {len(result.unmapped_components) - 5} more")

        return "\n".join(lines)
