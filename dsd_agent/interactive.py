"""Interactive mode for DSD Agent."""

import os
import sys
from pathlib import Path
from typing import Callable

from .agent import DSDAgent, MappingResult
from .pptx_handler import DSDDocument, ArchitectureSlide
from .image_analyzer import ArchitectureAnalysis, SystemComponent


class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'


def colored(text: str, color: str) -> str:
    """Apply color to text if terminal supports it."""
    if sys.stdout.isatty():
        return f"{color}{text}{Colors.RESET}"
    return text


def print_header(text: str):
    """Print a styled header."""
    print(f"\n{colored('═' * 60, Colors.CYAN)}")
    print(colored(f"  {text}", Colors.BOLD + Colors.CYAN))
    print(colored('═' * 60, Colors.CYAN))


def print_section(text: str):
    """Print a section header."""
    print(f"\n{colored('─' * 40, Colors.DIM)}")
    print(colored(f"  {text}", Colors.BOLD))
    print(colored('─' * 40, Colors.DIM))


def print_success(text: str):
    """Print success message."""
    print(colored(f"✓ {text}", Colors.GREEN))


def print_warning(text: str):
    """Print warning message."""
    print(colored(f"⚠ {text}", Colors.YELLOW))


def print_error(text: str):
    """Print error message."""
    print(colored(f"✗ {text}", Colors.RED))


def print_info(text: str):
    """Print info message."""
    print(colored(f"ℹ {text}", Colors.BLUE))


def prompt(text: str, default: str = "") -> str:
    """Prompt user for input."""
    if default:
        result = input(f"{text} [{default}]: ").strip()
        return result if result else default
    return input(f"{text}: ").strip()


def confirm(text: str, default: bool = True) -> bool:
    """Ask for yes/no confirmation."""
    suffix = "[Y/n]" if default else "[y/N]"
    response = input(f"{text} {suffix}: ").strip().lower()
    if not response:
        return default
    return response in ('y', 'yes')


def choose(text: str, options: list[str], allow_multiple: bool = False) -> list[int] | int:
    """Present options and get user choice."""
    print(f"\n{text}")
    for i, opt in enumerate(options, 1):
        print(f"  {colored(str(i), Colors.CYAN)}. {opt}")

    if allow_multiple:
        print(f"\n  Enter numbers separated by commas, or 'all' for all options")
        response = input("Choice: ").strip().lower()
        if response == 'all':
            return list(range(len(options)))
        try:
            return [int(x.strip()) - 1 for x in response.split(',') if x.strip()]
        except ValueError:
            return []
    else:
        while True:
            try:
                choice = int(input("Choice: ").strip()) - 1
                if 0 <= choice < len(options):
                    return choice
                print_error("Invalid choice, try again")
            except ValueError:
                print_error("Please enter a number")


class InteractiveSession:
    """Interactive session for populating DSD documents."""

    def __init__(self, api_key: str | None = None):
        self.agent = DSDAgent(api_key=api_key)
        self.document: DSDDocument | None = None
        self.analysis: ArchitectureAnalysis | None = None
        self.pending_mappings: list[MappingResult] = []

    def run(self):
        """Run the interactive session."""
        print_header("DSD Agent - Interactive Mode")
        print("Populate your Digital Solutioning Documents with architecture data\n")

        # Step 1: Load document
        if not self._step_load_document():
            return

        # Step 2: Select slides
        slides = self._step_select_slides()
        if not slides:
            return

        # Step 3: Provide architecture source
        if not self._step_provide_source():
            return

        # Step 4: Review extracted components
        self._step_review_components()

        # Step 5: Create and review mappings
        if not self._step_create_mappings(slides):
            return

        # Step 6: Apply and save
        self._step_apply_and_save()

    def _step_load_document(self) -> bool:
        """Step 1: Load the PowerPoint document."""
        print_section("Step 1: Load Document")

        while True:
            path = prompt("Enter path to PowerPoint file", "~/Downloads/*.pptx")
            path = os.path.expanduser(path)

            # Handle glob patterns
            if '*' in path:
                from glob import glob
                matches = glob(path)
                if not matches:
                    print_error(f"No files matching: {path}")
                    continue
                if len(matches) > 1:
                    print(f"Found {len(matches)} files:")
                    idx = choose("Select file:", matches)
                    path = matches[idx]
                else:
                    path = matches[0]

            if not os.path.exists(path):
                print_error(f"File not found: {path}")
                if not confirm("Try again?"):
                    return False
                continue

            try:
                summary = self.agent.load_document(path)
                self.document = self.agent.document
                print_success(f"Loaded: {Path(path).name}")
                print(f"\n{summary}")
                return True
            except Exception as e:
                print_error(f"Failed to load: {e}")
                if not confirm("Try again?"):
                    return False

    def _step_select_slides(self) -> list[ArchitectureSlide]:
        """Step 2: Select which slides to populate."""
        print_section("Step 2: Select Slides to Populate")

        slides = self.document.find_architecture_slides()
        if not slides:
            print_error("No slides with Lorem Ipsum placeholders found")
            return []

        options = []
        for s in slides:
            options.append(f"Slide {s.index + 1}: {s.title} ({len(s.placeholders)} placeholders)")

        selected_indices = choose(
            "Which slides do you want to populate?",
            options,
            allow_multiple=True
        )

        if isinstance(selected_indices, int):
            selected_indices = [selected_indices]

        selected = [slides[i] for i in selected_indices if 0 <= i < len(slides)]

        if selected:
            print_success(f"Selected {len(selected)} slide(s)")
        else:
            print_warning("No slides selected")

        return selected

    def _step_provide_source(self) -> bool:
        """Step 3: Provide architecture source."""
        print_section("Step 3: Provide Architecture Source")

        source_type = choose(
            "How would you like to provide architecture information?",
            [
                "Image file (whiteboard photo, diagram, screenshot)",
                "Mermaid diagram file (.mmd)",
                "Text notes (type or paste)",
                "Skip (use manual entry later)"
            ]
        )

        try:
            if source_type == 0:  # Image
                path = prompt("Enter path to image file")
                path = os.path.expanduser(path)
                if not os.path.exists(path):
                    print_error(f"File not found: {path}")
                    return False
                print_info("Analyzing image with Claude Vision...")
                self.analysis = self.agent.analyze_source(source_path=path)

            elif source_type == 1:  # Mermaid
                path = prompt("Enter path to mermaid file")
                path = os.path.expanduser(path)
                if not os.path.exists(path):
                    print_error(f"File not found: {path}")
                    return False
                with open(path) as f:
                    mermaid_code = f.read()
                print_info("Analyzing mermaid diagram...")
                self.analysis = self.agent.analyze_source(mermaid_code=mermaid_code)

            elif source_type == 2:  # Notes
                print("Enter architecture notes (press Enter twice to finish):")
                lines = []
                empty_count = 0
                while empty_count < 1:
                    line = input()
                    if not line:
                        empty_count += 1
                    else:
                        empty_count = 0
                        lines.append(line)
                notes = '\n'.join(lines)
                if not notes.strip():
                    print_error("No notes provided")
                    return False
                print_info("Analyzing notes...")
                self.analysis = self.agent.analyze_source(notes=notes)

            else:  # Skip
                print_warning("Skipping source analysis - you'll need to enter names manually")
                return True

            print_success(f"Extracted {len(self.analysis.components)} components")
            return True

        except Exception as e:
            print_error(f"Analysis failed: {e}")
            return confirm("Continue without analysis?")

    def _step_review_components(self):
        """Step 4: Review extracted components."""
        if not self.analysis:
            return

        print_section("Step 4: Review Extracted Components")

        # Group by category
        by_category: dict[str, list[SystemComponent]] = {}
        for comp in self.analysis.components:
            cat = comp.category or "other"
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(comp)

        for category, components in sorted(by_category.items()):
            print(f"\n  {colored(category.upper(), Colors.BOLD)} ({len(components)}):")
            for comp in components:
                layer_info = f" [{comp.layer}]" if comp.layer else ""
                print(f"    • {comp.name}{colored(layer_info, Colors.DIM)}")

        if confirm("\nWould you like to add or modify components?"):
            self._edit_components()

    def _edit_components(self):
        """Allow user to edit extracted components."""
        while True:
            action = choose(
                "What would you like to do?",
                ["Add a component", "Remove a component", "Done editing"]
            )

            if action == 0:  # Add
                name = prompt("Component name")
                category = prompt("Category (channel/integration/core_banking/data/external)", "integration")
                layer = prompt("Layer (presentation/application/data/infrastructure)", "")
                self.analysis.components.append(SystemComponent(
                    name=name,
                    category=category,
                    layer=layer,
                ))
                print_success(f"Added: {name}")

            elif action == 1:  # Remove
                options = [c.name for c in self.analysis.components]
                if not options:
                    print_warning("No components to remove")
                    continue
                idx = choose("Select component to remove:", options)
                removed = self.analysis.components.pop(idx)
                print_success(f"Removed: {removed.name}")

            else:  # Done
                break

    def _step_create_mappings(self, slides: list[ArchitectureSlide]) -> bool:
        """Step 5: Create and review mappings."""
        print_section("Step 5: Create Mappings")

        if not self.analysis:
            print_warning("No analysis available - entering manual mode")
            return self._manual_mapping_mode(slides)

        self.pending_mappings = []

        for slide in slides:
            print(f"\n{colored(f'Slide {slide.index + 1}: {slide.title}', Colors.BOLD)}")
            print_info("Creating mapping...")

            try:
                mapping = self.agent.create_mapping(slide, self.analysis)
                self.pending_mappings.append(mapping)

                # Show mapping
                print(f"  Mapped {len(mapping.mappings)} of {len(slide.placeholders)} placeholders:")
                for ph, comp in mapping.mappings[:10]:
                    print(f"    {colored(comp.name, Colors.GREEN)} → {ph.shape_name[-20:]}")
                if len(mapping.mappings) > 10:
                    print(f"    ... and {len(mapping.mappings) - 10} more")

                if mapping.unmapped_placeholders:
                    print_warning(f"  {len(mapping.unmapped_placeholders)} placeholders unmapped")

            except Exception as e:
                print_error(f"Mapping failed: {e}")
                if not confirm("Continue with other slides?"):
                    return False

        if not self.pending_mappings:
            print_error("No mappings created")
            return False

        return confirm("\nProceed with these mappings?")

    def _manual_mapping_mode(self, slides: list[ArchitectureSlide]) -> bool:
        """Allow manual entry for each placeholder."""
        print_info("Manual mode: Enter a name for each placeholder")

        self.pending_mappings = []

        for slide in slides:
            print(f"\n{colored(f'Slide {slide.index + 1}: {slide.title}', Colors.BOLD)}")

            mappings = []
            for ph in slide.placeholders:
                name = prompt(f"  [{ph.row_group + 1}] ({ph.left:.1f}, {ph.top:.1f})", "TBD")
                comp = SystemComponent(name=name, category="manual")
                mappings.append((ph, comp))

            self.pending_mappings.append(MappingResult(
                slide_index=slide.index,
                slide_title=slide.title,
                mappings=mappings,
                unmapped_placeholders=[],
                unmapped_components=[],
            ))

        return True

    def _step_apply_and_save(self):
        """Step 6: Apply mappings and save."""
        print_section("Step 6: Apply and Save")

        # Apply mappings
        total_updated = 0
        for mapping in self.pending_mappings:
            count = self.agent.apply_mapping(mapping)
            total_updated += count
            print_success(f"Updated {count} placeholders on slide {mapping.slide_index + 1}")

        # Save
        default_output = str(self.document.path.parent / f"{self.document.path.stem}_populated.pptx")
        output_path = prompt("Save to", default_output)
        output_path = os.path.expanduser(output_path)

        try:
            saved_path = self.agent.save_document(output_path)
            print_success(f"Saved to: {saved_path}")
            print(f"\n{colored('Done!', Colors.GREEN + Colors.BOLD)} Updated {total_updated} placeholders across {len(self.pending_mappings)} slides.")
        except Exception as e:
            print_error(f"Failed to save: {e}")


def run_interactive(api_key: str | None = None):
    """Entry point for interactive mode."""
    session = InteractiveSession(api_key=api_key)
    session.run()
