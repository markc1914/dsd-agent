# DSD Agent

Agent for populating Digital Solutioning Documents (DSD) with architecture data from photos, diagrams, and notes.

![DSD Agent GUI](https://img.shields.io/badge/GUI-Streamlit-FF4B4B?style=flat&logo=streamlit)
![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat&logo=python)
![Claude](https://img.shields.io/badge/AI-Claude-orange?style=flat)

## Features

- **Web GUI**: Modern Streamlit-based interface with drag-and-drop support
- **PowerPoint Support**: Read and update `.pptx` files with Lorem Ipsum placeholders
- **Google Slides Support**: Connect to Google Slides presentations via API
- **Multi-source Input**:
  - Whiteboard photos (analyzed with Claude Vision)
  - Mermaid diagram files
  - Text notes describing architecture
- **Integration Pattern Recognition**: Automatically detects enterprise integration patterns:
  - Messaging: Point-to-point, Pub/Sub, Message Broker
  - API: API Gateway, ESB, Service Mesh, BFF
  - Event: Event-Driven, Event Sourcing, CQRS
  - Microservices: Saga, Circuit Breaker, Strangler Fig
  - Data: Data Lake, Data Warehouse, CDC, ETL
- **Interactive CLI Mode**: Guided workflow for terminal users
- **Smart Mapping**: AI-powered mapping of components to slide placeholders based on position and context

## Installation

```bash
pip install -e .
```

For GUI support:
```bash
pip install -e ".[gui]"
```

For Google Slides support:
```bash
pip install -e ".[google]"
```

For everything:
```bash
pip install -e ".[all]"
```

## Usage

### Web GUI (Recommended)

```bash
streamlit run dsd_agent/gui.py
```

Then open http://localhost:8501 in your browser.

**GUI Features:**
- Drag-and-drop file upload
- Visual component extraction preview
- Interactive slide selection
- Live mapping preview
- One-click download of populated document

### CLI Interactive Mode

```bash
dsd-agent --interactive
```

### Command Line

```bash
# Analyze document structure
dsd-agent document.pptx --analyze-only

# Populate from whiteboard photo
dsd-agent document.pptx --image whiteboard.jpg

# Populate from mermaid diagram
dsd-agent document.pptx --mermaid architecture.mmd

# Populate from text notes
dsd-agent document.pptx --notes "Core Banking: T24, CRM: Salesforce..."

# Preview without saving (dry run)
dsd-agent document.pptx --image arch.png --dry-run

# Filter by slide type
dsd-agent document.pptx --image arch.png --filter "current"

# Google Slides
dsd-agent --google-slides PRESENTATION_ID --image arch.png
```

### Python API

```python
from dsd_agent import DSDAgent

agent = DSDAgent()

# Load document
agent.load_document("document.pptx")

# Analyze architecture source
analysis = agent.analyze_source(
    source_path="whiteboard.jpg",
    analyze_patterns=True  # Enable integration pattern detection
)

# Get integration pattern analysis
print(agent.get_integration_summary())

# Populate slides
results = agent.populate_all_slides(analysis, dry_run=True)

# Save
agent.save_document("output.pptx")
```

## Environment Variables

- `ANTHROPIC_API_KEY`: API key for Claude (required)
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to Google service account JSON (for Google Slides)

## Project Structure

```
dsd-agent/
├── dsd_agent/
│   ├── __init__.py
│   ├── agent.py              # Main agent logic
│   ├── cli.py                # Command-line interface
│   ├── gui.py                # Streamlit web GUI
│   ├── interactive.py        # CLI interactive mode
│   ├── pptx_handler.py       # PowerPoint handling
│   ├── google_slides.py      # Google Slides support
│   ├── image_analyzer.py     # Claude Vision integration
│   └── integration_patterns.py  # Pattern recognition
├── pyproject.toml
├── requirements.txt
└── README.md
```

## License

MIT
