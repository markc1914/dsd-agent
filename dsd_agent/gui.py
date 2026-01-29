"""Streamlit GUI for DSD Agent."""

import os
import tempfile
from pathlib import Path

import streamlit as st

# Must be first Streamlit command
st.set_page_config(
    page_title="DSD Agent",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

from dsd_agent.agent import DSDAgent
from dsd_agent.pptx_handler import DSDDocument
from dsd_agent.integration_patterns import format_pattern_summary


def init_session_state():
    """Initialize session state variables."""
    if "agent" not in st.session_state:
        st.session_state.agent = None
    if "document_loaded" not in st.session_state:
        st.session_state.document_loaded = False
    if "analysis" not in st.session_state:
        st.session_state.analysis = None
    if "mappings" not in st.session_state:
        st.session_state.mappings = []
    if "temp_file" not in st.session_state:
        st.session_state.temp_file = None
    if "step" not in st.session_state:
        st.session_state.step = 1


def render_sidebar():
    """Render the sidebar with API key and settings."""
    with st.sidebar:
        st.title("🏗️ DSD Agent")
        st.caption("Populate architecture diagrams from photos & notes")

        st.divider()

        # API Key
        api_key = st.text_input(
            "Anthropic API Key",
            type="password",
            value=os.environ.get("ANTHROPIC_API_KEY", ""),
            help="Required for analyzing images and creating mappings",
        )

        if api_key:
            os.environ["ANTHROPIC_API_KEY"] = api_key
            if st.session_state.agent is None:
                st.session_state.agent = DSDAgent(api_key=api_key)
            st.success("✓ API Key set")
        else:
            st.warning("⚠️ Enter API key to continue")

        st.divider()

        # Progress indicator
        st.subheader("Progress")
        steps = ["Upload Document", "Add Source", "Review & Map", "Download"]
        for i, step_name in enumerate(steps, 1):
            if i < st.session_state.step:
                st.write(f"✅ {step_name}")
            elif i == st.session_state.step:
                st.write(f"🔵 **{step_name}**")
            else:
                st.write(f"⚪ {step_name}")

        st.divider()

        # Reset button
        if st.button("🔄 Start Over", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

        st.divider()
        st.caption("Built with Claude & Streamlit")


def render_step1_upload():
    """Step 1: Upload document."""
    st.header("📄 Step 1: Upload Document")
    st.write("Upload your Digital Solutioning Document (PowerPoint) to get started.")

    col1, col2 = st.columns([2, 1])

    with col1:
        uploaded_file = st.file_uploader(
            "Choose a PowerPoint file",
            type=["pptx"],
            help="Upload your DSD template with Lorem Ipsum placeholders",
        )

        if uploaded_file:
            # Save to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pptx") as tmp:
                tmp.write(uploaded_file.getvalue())
                st.session_state.temp_file = tmp.name

            # Load document
            if st.session_state.agent:
                with st.spinner("Loading document..."):
                    summary = st.session_state.agent.load_document(st.session_state.temp_file)
                    st.session_state.document_loaded = True

                st.success(f"✓ Loaded: {uploaded_file.name}")

                # Show summary
                with st.expander("📊 Document Summary", expanded=True):
                    slides = st.session_state.agent.document.find_architecture_slides()

                    st.write(f"**{len(slides)} slides** with Lorem Ipsum placeholders:")

                    for slide in slides:
                        col_a, col_b = st.columns([3, 1])
                        with col_a:
                            st.write(f"• **Slide {slide.index + 1}**: {slide.title}")
                        with col_b:
                            st.write(f"{len(slide.placeholders)} placeholders")

                # Proceed button
                if st.button("Continue →", type="primary", use_container_width=True):
                    st.session_state.step = 2
                    st.rerun()
            else:
                st.error("Please enter your API key in the sidebar first.")

    with col2:
        st.info(
            "**Supported formats:**\n"
            "- PowerPoint (.pptx)\n\n"
            "**Requirements:**\n"
            "- Lorem Ipsum placeholders\n"
            "- Architecture diagram slides"
        )


def render_step2_source():
    """Step 2: Provide architecture source."""
    st.header("🎨 Step 2: Architecture Source")
    st.write("Provide the architecture information to populate your document.")

    # Back button
    if st.button("← Back to Upload"):
        st.session_state.step = 1
        st.rerun()

    st.divider()

    # Source type tabs
    tab1, tab2, tab3 = st.tabs(["📷 Image", "📝 Text Notes", "📊 Mermaid Diagram"])

    with tab1:
        st.write("Upload a whiteboard photo, architecture diagram, or screenshot.")

        uploaded_image = st.file_uploader(
            "Choose an image",
            type=["png", "jpg", "jpeg", "webp"],
            key="image_upload",
        )

        if uploaded_image:
            col1, col2 = st.columns([1, 1])
            with col1:
                st.image(uploaded_image, caption="Uploaded image", use_container_width=True)

            with col2:
                analyze_patterns = st.checkbox(
                    "Analyze integration patterns",
                    value=True,
                    help="Detect enterprise integration patterns in the architecture",
                )

                if st.button("🔍 Analyze Image", type="primary", use_container_width=True):
                    # Save image to temp file
                    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_image.name).suffix) as tmp:
                        tmp.write(uploaded_image.getvalue())
                        image_path = tmp.name

                    with st.spinner("Analyzing image with Claude Vision..."):
                        st.session_state.analysis = st.session_state.agent.analyze_source(
                            source_path=image_path,
                            analyze_patterns=analyze_patterns,
                        )

                    st.success(f"✓ Found {len(st.session_state.analysis.components)} components")
                    st.session_state.step = 3
                    st.rerun()

    with tab2:
        st.write("Describe your architecture in text format.")

        notes = st.text_area(
            "Architecture Notes",
            height=200,
            placeholder="""Example:
Channels: Mobile Banking App, Internet Banking, Branch Teller
Integration: API Gateway, ESB, Message Queue
Core Systems: Core Banking (T24), Card Management, Loan Origination
Data: Oracle Database, Data Warehouse
External: SWIFT, Credit Bureau, Payment Switch""",
        )

        col1, col2 = st.columns([1, 1])
        with col1:
            analyze_patterns = st.checkbox(
                "Analyze integration patterns",
                value=True,
                key="notes_patterns",
            )

        with col2:
            if st.button("🔍 Analyze Notes", type="primary", use_container_width=True, disabled=not notes):
                with st.spinner("Analyzing notes..."):
                    st.session_state.analysis = st.session_state.agent.analyze_source(
                        notes=notes,
                        analyze_patterns=analyze_patterns,
                    )

                st.success(f"✓ Found {len(st.session_state.analysis.components)} components")
                st.session_state.step = 3
                st.rerun()

    with tab3:
        st.write("Paste your Mermaid diagram code.")

        mermaid_code = st.text_area(
            "Mermaid Code",
            height=200,
            placeholder="""graph TD
    A[Mobile App] --> B[API Gateway]
    B --> C[Core Banking]
    B --> D[Card System]
    C --> E[(Database)]""",
        )

        col1, col2 = st.columns([1, 1])
        with col1:
            analyze_patterns = st.checkbox(
                "Analyze integration patterns",
                value=True,
                key="mermaid_patterns",
            )

        with col2:
            if st.button("🔍 Analyze Mermaid", type="primary", use_container_width=True, disabled=not mermaid_code):
                with st.spinner("Analyzing diagram..."):
                    st.session_state.analysis = st.session_state.agent.analyze_source(
                        mermaid_code=mermaid_code,
                        analyze_patterns=analyze_patterns,
                    )

                st.success(f"✓ Found {len(st.session_state.analysis.components)} components")
                st.session_state.step = 3
                st.rerun()


def render_step3_mapping():
    """Step 3: Review and create mappings."""
    st.header("🔗 Step 3: Review & Map")

    # Back button
    if st.button("← Back to Source"):
        st.session_state.step = 2
        st.rerun()

    st.divider()

    # Show extracted components
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("📦 Extracted Components")

        analysis = st.session_state.analysis

        # Group by category
        by_category = {}
        for comp in analysis.components:
            cat = comp.category or "other"
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(comp)

        for category, components in sorted(by_category.items()):
            with st.expander(f"**{category.upper()}** ({len(components)})", expanded=True):
                for comp in components:
                    st.write(f"• {comp.name}")
                    if comp.layer:
                        st.caption(f"  Layer: {comp.layer}")

    with col2:
        st.subheader("🔍 Integration Patterns")

        if st.session_state.agent._last_integration_analysis:
            patterns = st.session_state.agent._last_integration_analysis

            st.metric("Primary Pattern", patterns.primary_pattern.value)
            st.metric("Integration Style", patterns.integration_style.upper())

            with st.expander("All Detected Patterns", expanded=False):
                for p in patterns.patterns:
                    st.write(f"**{p.name}** ({p.pattern_type.value})")
                    st.caption(p.description)
                    st.progress(p.confidence)

            if patterns.recommended_technologies:
                with st.expander("Recommended Technologies"):
                    for tech in patterns.recommended_technologies:
                        st.write(f"• {tech}")
        else:
            st.info("Pattern analysis not performed")

    st.divider()

    # Slide selection
    st.subheader("📊 Select Slides to Populate")

    slides = st.session_state.agent.document.find_architecture_slides()

    selected_slides = []
    cols = st.columns(min(len(slides), 3))

    for i, slide in enumerate(slides):
        with cols[i % 3]:
            if st.checkbox(
                f"Slide {slide.index + 1}",
                value=True,
                key=f"slide_{slide.index}",
            ):
                selected_slides.append(slide)
            st.caption(f"{slide.title[:30]}...")
            st.caption(f"{len(slide.placeholders)} placeholders")

    st.divider()

    # Create mappings
    col1, col2 = st.columns([1, 1])

    with col1:
        dry_run = st.checkbox("Preview only (don't save)", value=True)

    with col2:
        if st.button("🚀 Create Mappings", type="primary", use_container_width=True, disabled=not selected_slides):
            st.session_state.mappings = []

            progress_bar = st.progress(0)
            status_text = st.empty()

            for i, slide in enumerate(selected_slides):
                status_text.write(f"Processing slide {slide.index + 1}: {slide.title}...")

                mapping = st.session_state.agent.create_mapping(slide, analysis)

                if not dry_run:
                    st.session_state.agent.apply_mapping(mapping)

                st.session_state.mappings.append(mapping)
                progress_bar.progress((i + 1) / len(selected_slides))

            status_text.write("✓ Mappings complete!")
            st.session_state.step = 4
            st.rerun()


def render_step4_download():
    """Step 4: Review mappings and download."""
    st.header("✅ Step 4: Review & Download")

    # Back button
    if st.button("← Back to Mapping"):
        st.session_state.step = 3
        st.rerun()

    st.divider()

    # Show mapping results
    st.subheader("📋 Mapping Results")

    for mapping in st.session_state.mappings:
        with st.expander(f"**Slide {mapping.slide_index + 1}**: {mapping.slide_title}", expanded=True):
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Mapped", len(mapping.mappings))
            with col2:
                st.metric("Unmapped Placeholders", len(mapping.unmapped_placeholders))
            with col3:
                st.metric("Unused Components", len(mapping.unmapped_components))

            # Show mappings table
            if mapping.mappings:
                st.write("**Mappings:**")
                data = []
                for ph, comp in mapping.mappings:
                    data.append({
                        "Component": comp.name,
                        "Position": f"({ph.left:.1f}, {ph.top:.1f})",
                        "Row": ph.row_group + 1,
                    })
                st.dataframe(data, use_container_width=True)

            # Show integration patterns if available
            if mapping.integration_patterns:
                st.write("**Integration Patterns:**")
                for p in mapping.integration_patterns[:3]:
                    st.write(f"• {p.name} ({p.pattern_type.value})")

    st.divider()

    # Save and download
    st.subheader("💾 Save Document")

    col1, col2 = st.columns([2, 1])

    with col1:
        output_name = st.text_input(
            "Output filename",
            value="populated_document.pptx",
        )

    with col2:
        if st.button("📥 Generate & Download", type="primary", use_container_width=True):
            with st.spinner("Generating document..."):
                # Apply mappings if not already done
                for mapping in st.session_state.mappings:
                    st.session_state.agent.apply_mapping(mapping)

                # Save to temp file
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pptx") as tmp:
                    output_path = st.session_state.agent.save_document(tmp.name)

                # Read file for download
                with open(output_path, "rb") as f:
                    file_bytes = f.read()

                st.download_button(
                    label="⬇️ Download PPTX",
                    data=file_bytes,
                    file_name=output_name,
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    use_container_width=True,
                )

    st.divider()

    # Summary
    st.subheader("📊 Summary")

    total_mapped = sum(len(m.mappings) for m in st.session_state.mappings)
    total_slides = len(st.session_state.mappings)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Slides Processed", total_slides)
    with col2:
        st.metric("Placeholders Mapped", total_mapped)
    with col3:
        st.metric("Components Used", len(st.session_state.analysis.components))

    st.success("🎉 Document populated successfully!")


def main():
    """Main entry point for the Streamlit app."""
    init_session_state()
    render_sidebar()

    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        st.warning("👈 Please enter your Anthropic API key in the sidebar to get started.")
        st.stop()

    # Render current step
    if st.session_state.step == 1:
        render_step1_upload()
    elif st.session_state.step == 2:
        render_step2_source()
    elif st.session_state.step == 3:
        render_step3_mapping()
    elif st.session_state.step == 4:
        render_step4_download()


if __name__ == "__main__":
    main()
