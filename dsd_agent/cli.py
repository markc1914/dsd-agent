"""Command-line interface for DSD Agent."""

import argparse
import os
import sys
from pathlib import Path

from .agent import DSDAgent


def main():
    parser = argparse.ArgumentParser(
        description="DSD Agent - Populate Digital Solutioning Documents with architecture data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (recommended for first-time use)
  dsd-agent --interactive

  # Populate PowerPoint from a whiteboard photo
  dsd-agent document.pptx --image whiteboard.jpg

  # Populate Google Slides from a mermaid diagram
  dsd-agent --google-slides PRESENTATION_ID --mermaid diagram.mmd

  # Populate from text notes
  dsd-agent document.pptx --notes "Core Banking: Temenos T24, CRM: Salesforce..."

  # Preview changes without saving (dry run)
  dsd-agent document.pptx --image arch.png --dry-run

  # Only populate current state slides
  dsd-agent document.pptx --image arch.png --filter "current"

Environment Variables:
  ANTHROPIC_API_KEY           API key for Claude (required for analysis)
  GOOGLE_APPLICATION_CREDENTIALS  Path to Google service account JSON (for Google Slides)
""",
    )

    # Document source (mutually exclusive)
    doc_group = parser.add_mutually_exclusive_group()
    doc_group.add_argument(
        "document",
        type=str,
        nargs="?",
        help="Path to the PowerPoint document (.pptx)",
    )
    doc_group.add_argument(
        "--google-slides", "-g",
        type=str,
        metavar="PRESENTATION_ID",
        help="Google Slides presentation ID",
    )
    doc_group.add_argument(
        "--interactive", "-I",
        action="store_true",
        help="Run in interactive mode with guided workflow",
    )

    # Architecture source
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument(
        "--image", "-i",
        type=str,
        help="Path to architecture image (whiteboard photo, diagram, etc.)",
    )
    source_group.add_argument(
        "--mermaid", "-m",
        type=str,
        help="Path to mermaid diagram file (.mmd)",
    )
    source_group.add_argument(
        "--notes", "-n",
        type=str,
        help="Text notes describing the architecture",
    )
    source_group.add_argument(
        "--analyze-only",
        action="store_true",
        help="Only analyze the document structure, don't populate",
    )

    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output file path (default: adds _populated suffix)",
    )

    parser.add_argument(
        "--filter", "-f",
        type=str,
        help="Filter slides by type (e.g., 'current', 'target')",
    )

    parser.add_argument(
        "--slide", "-s",
        type=int,
        help="Populate only a specific slide number (1-indexed)",
    )

    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="Preview mappings without saving changes",
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output",
    )

    parser.add_argument(
        "--api-key",
        type=str,
        help="Anthropic API key (or set ANTHROPIC_API_KEY env var)",
    )

    parser.add_argument(
        "--credentials",
        type=str,
        help="Path to Google credentials JSON file",
    )

    args = parser.parse_args()

    # Get API key
    api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY")

    # Interactive mode
    if args.interactive:
        from .interactive import run_interactive
        run_interactive(api_key=api_key)
        return

    # Check document source
    if not args.document and not args.google_slides:
        parser.print_help()
        print("\nError: Must provide a document path, --google-slides, or use --interactive mode")
        sys.exit(1)

    # Google Slides mode
    if args.google_slides:
        run_google_slides_mode(args, api_key)
        return

    # PowerPoint mode
    run_pptx_mode(args, api_key)


def run_pptx_mode(args, api_key: str | None):
    """Run in PowerPoint mode."""
    doc_path = Path(args.document).expanduser()
    if not doc_path.exists():
        print(f"Error: Document not found: {doc_path}", file=sys.stderr)
        sys.exit(1)

    # Check if API key is needed
    needs_api_key = args.image or args.mermaid or args.notes
    if needs_api_key and not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable not set.", file=sys.stderr)
        print("Set it with: export ANTHROPIC_API_KEY='your-key'", file=sys.stderr)
        print("Or use: --api-key 'your-key'", file=sys.stderr)
        sys.exit(1)

    # Initialize agent
    agent = DSDAgent(api_key=api_key)

    # Load document
    print(f"Loading document: {doc_path.name}")
    summary = agent.load_document(doc_path)
    print(summary)

    if args.analyze_only:
        return

    # Analyze source
    analysis = analyze_source(agent, args)
    if analysis is None:
        return

    # Create mappings
    print("\nCreating mappings...")

    if args.slide:
        # Single slide mode
        slide_index = args.slide - 1
        result = agent.populate_slide(slide_index, analysis, dry_run=args.dry_run)
        results = [result]
    else:
        # All slides mode
        results = agent.populate_all_slides(
            analysis,
            slide_type_filter=args.filter,
            dry_run=args.dry_run,
        )

    # Display results
    for result in results:
        print(agent.get_mapping_summary(result))

    # Save if not dry run
    if not args.dry_run:
        output_path = agent.save_document(args.output)
        print(f"\nSaved to: {output_path}")
    else:
        print("\n[DRY RUN] No changes saved")


def run_google_slides_mode(args, api_key: str | None):
    """Run in Google Slides mode."""
    # Check if API key is needed
    needs_api_key = args.image or args.mermaid or args.notes
    if needs_api_key and not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    try:
        from .google_slides import GoogleSlidesAgent
    except ImportError as e:
        print(f"Error: Google Slides support not available: {e}", file=sys.stderr)
        print("Install with: pip install google-api-python-client google-auth-oauthlib", file=sys.stderr)
        sys.exit(1)

    credentials_path = args.credentials or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

    # Initialize Google Slides agent
    gs_agent = GoogleSlidesAgent(
        api_key=api_key,
        credentials_path=credentials_path,
    )

    # Load presentation
    print(f"Loading Google Slides presentation: {args.google_slides}")
    summary = gs_agent.load_presentation(args.google_slides)
    print(summary)

    if args.analyze_only:
        return

    # Analyze source
    analysis = analyze_source(gs_agent, args)
    if analysis is None:
        return

    # Create and apply mappings
    print("\nCreating mappings...")

    if args.slide:
        slide_index = args.slide - 1
        result = gs_agent.populate_slide(slide_index, analysis, dry_run=args.dry_run)
        results = [result]
    else:
        results = gs_agent.populate_all_slides(
            analysis,
            slide_type_filter=args.filter,
            dry_run=args.dry_run,
        )

    # Display results
    for result in results:
        print(gs_agent.get_mapping_summary(result))

    if not args.dry_run:
        print("\nChanges applied to Google Slides")
    else:
        print("\n[DRY RUN] No changes saved")


def analyze_source(agent, args):
    """Analyze architecture source and return analysis."""
    print("\nAnalyzing architecture source...")

    if args.image:
        image_path = Path(args.image).expanduser()
        if not image_path.exists():
            print(f"Error: Image not found: {image_path}", file=sys.stderr)
            sys.exit(1)
        analysis = agent.analyze_source(source_path=image_path)
        print(f"  Source type: {analysis.source_type}")
        print(f"  Found {len(analysis.components)} components")

    elif args.mermaid:
        mermaid_path = Path(args.mermaid).expanduser()
        if not mermaid_path.exists():
            print(f"Error: Mermaid file not found: {mermaid_path}", file=sys.stderr)
            sys.exit(1)
        with open(mermaid_path) as f:
            mermaid_code = f.read()
        analysis = agent.analyze_source(mermaid_code=mermaid_code)
        print(f"  Found {len(analysis.components)} components")

    elif args.notes:
        analysis = agent.analyze_source(notes=args.notes)
        print(f"  Found {len(analysis.components)} components")

    else:
        print("Error: Must provide --image, --mermaid, or --notes", file=sys.stderr)
        sys.exit(1)

    if args.verbose:
        print("\nExtracted components:")
        for comp in analysis.components:
            print(f"  - {comp.name} ({comp.category})")

    return analysis


if __name__ == "__main__":
    main()
