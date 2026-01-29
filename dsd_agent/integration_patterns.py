"""Integration pattern recognition and handling for DSD Agent."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import anthropic


class IntegrationPatternType(Enum):
    """Common enterprise integration patterns."""
    # Messaging Patterns
    POINT_TO_POINT = "point_to_point"
    PUBLISH_SUBSCRIBE = "publish_subscribe"
    REQUEST_REPLY = "request_reply"
    MESSAGE_BROKER = "message_broker"

    # Integration Layer Patterns
    API_GATEWAY = "api_gateway"
    ESB = "enterprise_service_bus"
    SERVICE_MESH = "service_mesh"
    BFF = "backend_for_frontend"

    # Event Patterns
    EVENT_DRIVEN = "event_driven"
    EVENT_SOURCING = "event_sourcing"
    CQRS = "cqrs"

    # Microservices Patterns
    SAGA = "saga"
    CIRCUIT_BREAKER = "circuit_breaker"
    SIDECAR = "sidecar"
    STRANGLER_FIG = "strangler_fig"

    # Data Patterns
    DATA_LAKE = "data_lake"
    DATA_WAREHOUSE = "data_warehouse"
    CDC = "change_data_capture"
    ETL = "etl"

    # Security Patterns
    OAUTH_OIDC = "oauth_oidc"
    API_KEY = "api_key"
    MTLS = "mtls"
    ZERO_TRUST = "zero_trust"

    # Other
    BATCH = "batch"
    REAL_TIME = "real_time"
    HYBRID = "hybrid"
    UNKNOWN = "unknown"


@dataclass
class IntegrationPattern:
    """Represents a detected integration pattern."""
    pattern_type: IntegrationPatternType
    name: str
    description: str
    components_involved: list[str] = field(default_factory=list)
    data_flow: str = ""
    protocols: list[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class IntegrationAnalysis:
    """Result of analyzing integration patterns in an architecture."""
    patterns: list[IntegrationPattern]
    primary_pattern: IntegrationPatternType
    integration_style: str  # "sync", "async", "hybrid"
    recommended_technologies: list[str]
    concerns: list[str]
    raw_analysis: str


# Pattern templates for common banking/financial services architectures
BANKING_INTEGRATION_TEMPLATES = {
    "core_banking_integration": {
        "patterns": [IntegrationPatternType.ESB, IntegrationPatternType.REQUEST_REPLY],
        "description": "Integration with core banking system",
        "typical_components": ["Core Banking", "ESB", "API Gateway", "Channel Apps"],
        "protocols": ["ISO 8583", "ISO 20022", "SOAP", "REST"],
    },
    "payment_processing": {
        "patterns": [IntegrationPatternType.MESSAGE_BROKER, IntegrationPatternType.SAGA],
        "description": "Payment processing and settlement",
        "typical_components": ["Payment Gateway", "Card Processor", "SWIFT", "Settlement"],
        "protocols": ["ISO 8583", "ISO 20022", "SWIFT MT/MX"],
    },
    "open_banking": {
        "patterns": [IntegrationPatternType.API_GATEWAY, IntegrationPatternType.OAUTH_OIDC],
        "description": "Open Banking / PSD2 compliant APIs",
        "typical_components": ["API Gateway", "Consent Manager", "TPP Portal", "AIS/PIS Services"],
        "protocols": ["REST", "OAuth 2.0", "OpenID Connect"],
    },
    "event_driven_banking": {
        "patterns": [IntegrationPatternType.EVENT_DRIVEN, IntegrationPatternType.PUBLISH_SUBSCRIBE],
        "description": "Event-driven architecture for real-time processing",
        "typical_components": ["Event Bus", "Event Store", "Consumers", "Producers"],
        "protocols": ["Kafka", "AMQP", "CloudEvents"],
    },
    "data_analytics": {
        "patterns": [IntegrationPatternType.DATA_LAKE, IntegrationPatternType.ETL],
        "description": "Data analytics and reporting infrastructure",
        "typical_components": ["Data Lake", "Data Warehouse", "ETL Pipeline", "BI Tools"],
        "protocols": ["JDBC", "Spark", "Airflow"],
    },
}


class IntegrationPatternAnalyzer:
    """Analyzes architecture for integration patterns."""

    ANALYSIS_PROMPT = """You are an expert enterprise integration architect specializing in banking and financial services.

Analyze the following architecture components and identify integration patterns.

COMPONENTS:
{components}

For each integration pattern you identify, provide:
1. Pattern type (from: point_to_point, publish_subscribe, request_reply, message_broker, api_gateway, enterprise_service_bus, service_mesh, backend_for_frontend, event_driven, event_sourcing, cqrs, saga, circuit_breaker, sidecar, strangler_fig, data_lake, data_warehouse, change_data_capture, etl, oauth_oidc, api_key, mtls, zero_trust, batch, real_time, hybrid)
2. Name for this integration
3. Description of how it works
4. Components involved
5. Data flow direction
6. Protocols/standards used
7. Confidence level (0.0 to 1.0)

Also identify:
- The primary/dominant integration pattern
- Overall integration style (sync, async, or hybrid)
- Recommended technologies based on the patterns
- Any concerns or anti-patterns detected

Return as JSON:
{{
    "patterns": [
        {{
            "pattern_type": "pattern_type_value",
            "name": "Integration Name",
            "description": "How it works",
            "components_involved": ["Component1", "Component2"],
            "data_flow": "Component1 -> Component2",
            "protocols": ["REST", "Kafka"],
            "confidence": 0.9
        }}
    ],
    "primary_pattern": "dominant_pattern_type",
    "integration_style": "sync|async|hybrid",
    "recommended_technologies": ["Technology1", "Technology2"],
    "concerns": ["Any anti-patterns or issues detected"]
}}

Return ONLY the JSON."""

    def __init__(self, api_key: str | None = None):
        self.client = anthropic.Anthropic(api_key=api_key)

    def analyze_components(self, components: list[Any]) -> IntegrationAnalysis:
        """Analyze a list of components for integration patterns."""
        # Format components for the prompt
        comp_lines = []
        for comp in components:
            if hasattr(comp, 'name'):
                line = f"- {comp.name}"
                if hasattr(comp, 'category') and comp.category:
                    line += f" (Category: {comp.category})"
                if hasattr(comp, 'layer') and comp.layer:
                    line += f" [Layer: {comp.layer}]"
                if hasattr(comp, 'description') and comp.description:
                    line += f"\n  Description: {comp.description}"
                comp_lines.append(line)
            else:
                comp_lines.append(f"- {comp}")

        prompt = self.ANALYSIS_PROMPT.format(components="\n".join(comp_lines))

        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text

        # Parse JSON
        import json
        import re

        try:
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            data = json.loads(response_text.strip())
        except json.JSONDecodeError:
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                data = json.loads(json_match.group())
            else:
                raise ValueError(f"Could not parse integration analysis")

        # Build result
        patterns = []
        for p in data.get("patterns", []):
            try:
                pattern_type = IntegrationPatternType(p.get("pattern_type", "unknown"))
            except ValueError:
                pattern_type = IntegrationPatternType.UNKNOWN

            patterns.append(IntegrationPattern(
                pattern_type=pattern_type,
                name=p.get("name", "Unknown"),
                description=p.get("description", ""),
                components_involved=p.get("components_involved", []),
                data_flow=p.get("data_flow", ""),
                protocols=p.get("protocols", []),
                confidence=p.get("confidence", 0.5),
            ))

        try:
            primary_pattern = IntegrationPatternType(data.get("primary_pattern", "unknown"))
        except ValueError:
            primary_pattern = IntegrationPatternType.UNKNOWN

        return IntegrationAnalysis(
            patterns=patterns,
            primary_pattern=primary_pattern,
            integration_style=data.get("integration_style", "hybrid"),
            recommended_technologies=data.get("recommended_technologies", []),
            concerns=data.get("concerns", []),
            raw_analysis=response_text,
        )

    def suggest_patterns_for_slide(
        self,
        slide_title: str,
        components: list[Any],
    ) -> list[IntegrationPattern]:
        """Suggest appropriate integration patterns for a specific slide."""
        title_lower = slide_title.lower()

        # Check if this is an integration-focused slide
        if any(kw in title_lower for kw in ["integration", "connect", "interface", "api"]):
            analysis = self.analyze_components(components)
            return analysis.patterns

        # Check for specific architecture types
        if "current state" in title_lower:
            # Likely showing existing patterns
            return self._detect_legacy_patterns(components)

        if "target state" in title_lower or "future" in title_lower:
            # Likely showing modern patterns
            return self._suggest_modern_patterns(components)

        return []

    def _detect_legacy_patterns(self, components: list[Any]) -> list[IntegrationPattern]:
        """Detect patterns typical in legacy architectures."""
        patterns = []
        comp_names = [c.name.lower() if hasattr(c, 'name') else str(c).lower() for c in components]

        # Check for ESB
        if any("esb" in n or "bus" in n for n in comp_names):
            patterns.append(IntegrationPattern(
                pattern_type=IntegrationPatternType.ESB,
                name="Enterprise Service Bus",
                description="Centralized integration hub for legacy systems",
                confidence=0.9,
            ))

        # Check for point-to-point
        if any("direct" in n or "connector" in n for n in comp_names):
            patterns.append(IntegrationPattern(
                pattern_type=IntegrationPatternType.POINT_TO_POINT,
                name="Point-to-Point Integration",
                description="Direct connections between systems",
                confidence=0.7,
            ))

        # Check for batch processing
        if any("batch" in n or "etl" in n or "scheduler" in n for n in comp_names):
            patterns.append(IntegrationPattern(
                pattern_type=IntegrationPatternType.BATCH,
                name="Batch Processing",
                description="Scheduled batch data transfers",
                confidence=0.8,
            ))

        return patterns

    def _suggest_modern_patterns(self, components: list[Any]) -> list[IntegrationPattern]:
        """Suggest modern integration patterns for target architecture."""
        patterns = []
        comp_names = [c.name.lower() if hasattr(c, 'name') else str(c).lower() for c in components]

        # Check for API Gateway
        if any("api" in n or "gateway" in n for n in comp_names):
            patterns.append(IntegrationPattern(
                pattern_type=IntegrationPatternType.API_GATEWAY,
                name="API Gateway",
                description="Centralized API management and routing",
                protocols=["REST", "GraphQL", "gRPC"],
                confidence=0.9,
            ))

        # Check for event-driven
        if any("event" in n or "kafka" in n or "queue" in n or "message" in n for n in comp_names):
            patterns.append(IntegrationPattern(
                pattern_type=IntegrationPatternType.EVENT_DRIVEN,
                name="Event-Driven Architecture",
                description="Asynchronous event-based communication",
                protocols=["Kafka", "AMQP", "CloudEvents"],
                confidence=0.85,
            ))

        # Check for microservices patterns
        if len(components) > 10:
            patterns.append(IntegrationPattern(
                pattern_type=IntegrationPatternType.SERVICE_MESH,
                name="Service Mesh",
                description="Infrastructure layer for service-to-service communication",
                protocols=["Istio", "Linkerd", "Envoy"],
                confidence=0.6,
            ))

        return patterns

    def get_pattern_recommendations(
        self,
        analysis: IntegrationAnalysis,
    ) -> dict[str, Any]:
        """Get detailed recommendations based on pattern analysis."""
        recommendations = {
            "summary": "",
            "architecture_style": "",
            "key_technologies": [],
            "implementation_order": [],
            "risks": [],
        }

        # Determine overall architecture style
        if analysis.integration_style == "async":
            recommendations["architecture_style"] = "Event-Driven Architecture"
            recommendations["key_technologies"] = ["Apache Kafka", "RabbitMQ", "Redis Streams"]
        elif analysis.integration_style == "sync":
            recommendations["architecture_style"] = "API-First Architecture"
            recommendations["key_technologies"] = ["Kong", "Apigee", "AWS API Gateway"]
        else:
            recommendations["architecture_style"] = "Hybrid Integration Platform"
            recommendations["key_technologies"] = ["MuleSoft", "Boomi", "Azure Integration Services"]

        # Build summary
        pattern_names = [p.name for p in analysis.patterns[:3]]
        recommendations["summary"] = (
            f"Architecture primarily uses {analysis.primary_pattern.value} pattern "
            f"with {analysis.integration_style} communication style. "
            f"Key patterns identified: {', '.join(pattern_names)}."
        )

        # Implementation order based on dependencies
        if IntegrationPatternType.API_GATEWAY in [p.pattern_type for p in analysis.patterns]:
            recommendations["implementation_order"].append("1. API Gateway setup")

        if IntegrationPatternType.MESSAGE_BROKER in [p.pattern_type for p in analysis.patterns]:
            recommendations["implementation_order"].append("2. Message broker deployment")

        recommendations["implementation_order"].append("3. Service integration")
        recommendations["implementation_order"].append("4. Monitoring and observability")

        # Risks from concerns
        recommendations["risks"] = analysis.concerns

        return recommendations


def format_pattern_summary(analysis: IntegrationAnalysis) -> str:
    """Format integration analysis as a readable summary."""
    lines = [
        "\nIntegration Pattern Analysis",
        "=" * 40,
        f"\nPrimary Pattern: {analysis.primary_pattern.value}",
        f"Integration Style: {analysis.integration_style}",
        f"\nPatterns Detected ({len(analysis.patterns)}):",
    ]

    for p in analysis.patterns:
        lines.append(f"\n  {p.name} ({p.pattern_type.value})")
        lines.append(f"    {p.description}")
        if p.components_involved:
            lines.append(f"    Components: {', '.join(p.components_involved)}")
        if p.protocols:
            lines.append(f"    Protocols: {', '.join(p.protocols)}")
        lines.append(f"    Confidence: {p.confidence:.0%}")

    if analysis.recommended_technologies:
        lines.append(f"\nRecommended Technologies:")
        for tech in analysis.recommended_technologies:
            lines.append(f"  - {tech}")

    if analysis.concerns:
        lines.append(f"\nConcerns:")
        for concern in analysis.concerns:
            lines.append(f"  ! {concern}")

    return "\n".join(lines)
