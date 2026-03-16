"""Responsible AI guardrails with symbolic validation.

Demonstrates the neurosymbolic pattern from sample-why-agents-fail:
symbolic rules intercept tool calls before execution, enforcing constraints
that prompt-only approaches cannot guarantee. Maps to AIF-C01 Domain 4
(Guidelines for Responsible AI).

Ported from aws-samples/sample-why-agents-fail, adapted to project conventions.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Tuple

import click
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("guardrails")


# ---------------------------------------------------------------------------
# Rule engine
# ---------------------------------------------------------------------------


@dataclass
class GuardrailRule:
    """A symbolic constraint that must hold before a tool executes."""

    name: str
    condition: Callable[[Dict[str, Any]], bool]
    message: str
    severity: str = "block"  # block, warn, log


@dataclass
class GuardrailRuleset:
    """Collection of rules scoped to a tool or applied globally."""

    tool_name: str
    rules: List[GuardrailRule] = field(default_factory=list)

    def add_rule(
        self,
        name: str,
        condition: Callable[[Dict[str, Any]], bool],
        message: str,
        severity: str = "block",
    ) -> None:
        """Add a rule to this ruleset."""
        self.rules.append(
            GuardrailRule(
                name=name,
                condition=condition,
                message=message,
                severity=severity,
            )
        )


def validate_rules(
    rules: List[GuardrailRule],
    context: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """Evaluate all rules against context, returning (passed, violations)."""
    violations = []
    for rule in rules:
        try:
            if not rule.condition(context):
                violations.append(f"[{rule.severity}] {rule.name}: {rule.message}")
        except Exception as evaluation_error:
            violations.append(
                f"[error] {rule.name}: rule evaluation failed: {evaluation_error}"
            )
    return len(violations) == 0, violations


# ---------------------------------------------------------------------------
# Guardrail engine
# ---------------------------------------------------------------------------


class ValidationResult(BaseModel):
    """Result of validating a tool call against guardrails."""

    tool_name: str
    allowed: bool
    violations: List[str] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)


class GuardrailEngine:
    """Validates tool calls against symbolic rules before execution.

    This implements the neurosymbolic pattern: LLM decides *what* to do,
    symbolic rules verify it's *allowed*. The LLM cannot bypass these
    constraints regardless of prompt injection attempts.
    """

    def __init__(self) -> None:
        self._rulesets: Dict[str, GuardrailRuleset] = {}
        self._global_rules: List[GuardrailRule] = []
        self._audit_log: List[ValidationResult] = []

    def add_ruleset(self, ruleset: GuardrailRuleset) -> None:
        """Register a ruleset for a specific tool."""
        self._rulesets[ruleset.tool_name] = ruleset

    def add_global_rule(
        self,
        name: str,
        condition: Callable[[Dict[str, Any]], bool],
        message: str,
        severity: str = "block",
    ) -> None:
        """Add a rule that applies to all tool calls."""
        self._global_rules.append(
            GuardrailRule(
                name=name,
                condition=condition,
                message=message,
                severity=severity,
            )
        )

    def validate(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
    ) -> ValidationResult:
        """Check a tool call against all applicable rules."""
        context = {"tool_name": tool_name, **tool_input}
        all_violations: List[str] = []

        # Global rules
        _, global_violations = validate_rules(self._global_rules, context)
        all_violations.extend(global_violations)

        # Tool-specific rules
        if tool_name in self._rulesets:
            _, tool_violations = validate_rules(
                self._rulesets[tool_name].rules, context
            )
            all_violations.extend(tool_violations)

        blocking_violations = [
            violation for violation in all_violations if violation.startswith("[block]")
        ]

        result = ValidationResult(
            tool_name=tool_name,
            allowed=len(blocking_violations) == 0,
            violations=all_violations,
            context=context,
        )
        self._audit_log.append(result)

        if all_violations:
            logger.warning(
                "Tool %s: %d violation(s): %s",
                tool_name,
                len(all_violations),
                "; ".join(all_violations),
            )

        return result

    @property
    def audit_log(self) -> List[ValidationResult]:
        """Access the audit trail of all validation checks."""
        return self._audit_log


# ---------------------------------------------------------------------------
# AWS Responsible AI pillar rules
# ---------------------------------------------------------------------------


def build_responsible_ai_engine() -> GuardrailEngine:
    """Build a guardrail engine with rules aligned to AWS responsible AI pillars.

    The eight pillars from the AWS Responsible AI framework:
      1. Fairness      5. Veracity & robustness
      2. Explainability  6. Safety
      3. Privacy & security  7. Controllability
      4. Transparency   8. Governance
    """
    engine = GuardrailEngine()

    # Pillar 1: Fairness — prevent demographic targeting
    engine.add_global_rule(
        name="no_demographic_targeting",
        condition=lambda ctx: not any(
            term in json.dumps(ctx).lower()
            for term in ["race", "ethnicity", "gender", "religion"]
        ),
        message="Input references protected demographic attributes",
        severity="block",
    )

    # Pillar 3: Privacy — block PII patterns
    engine.add_global_rule(
        name="no_pii_in_input",
        condition=lambda ctx: not any(
            term in json.dumps(ctx).lower()
            for term in ["ssn", "social security", "credit card", "passport number"]
        ),
        message="Input contains potential PII patterns",
        severity="block",
    )

    # Pillar 6: Safety — limit scope of dangerous operations
    engine.add_global_rule(
        name="no_destructive_operations",
        condition=lambda ctx: ctx.get("tool_name", "")
        not in [
            "delete_all",
            "drop_table",
            "format_disk",
        ],
        message="Destructive operation blocked by safety guardrail",
        severity="block",
    )

    # Pillar 7: Controllability — rate limiting
    call_counts: Dict[str, int] = {}

    def rate_limit_check(ctx: Dict[str, Any]) -> bool:
        tool_name = ctx.get("tool_name", "unknown")
        call_counts[tool_name] = call_counts.get(tool_name, 0) + 1
        return call_counts[tool_name] <= 50

    engine.add_global_rule(
        name="rate_limit",
        condition=rate_limit_check,
        message="Tool call rate limit exceeded (max 50 per session)",
        severity="warn",
    )

    return engine


# ---------------------------------------------------------------------------
# Example domain rules
# ---------------------------------------------------------------------------


def build_booking_rules() -> GuardrailRuleset:
    """Example domain-specific rules for a hotel booking tool."""
    ruleset = GuardrailRuleset(tool_name="book_hotel")

    ruleset.add_rule(
        name="max_guests",
        condition=lambda ctx: ctx.get("guests", 1) <= 10,
        message="Maximum 10 guests per booking",
    )

    ruleset.add_rule(
        name="max_nights",
        condition=lambda ctx: ctx.get("nights", 1) <= 30,
        message="Maximum 30 nights per booking",
    )

    ruleset.add_rule(
        name="positive_guests",
        condition=lambda ctx: ctx.get("guests", 1) > 0,
        message="Guest count must be positive",
    )

    return ruleset


def build_data_access_rules() -> GuardrailRuleset:
    """Example rules for a data query tool."""
    ruleset = GuardrailRuleset(tool_name="query_data")

    ruleset.add_rule(
        name="limit_result_size",
        condition=lambda ctx: ctx.get("limit", 100) <= 1000,
        message="Query result limit cannot exceed 1000 rows",
    )

    ruleset.add_rule(
        name="no_select_star",
        condition=lambda ctx: "select *" not in ctx.get("query", "").lower(),
        message="SELECT * queries are not permitted; specify columns explicitly",
    )

    return ruleset


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.group()
def cli():
    """Responsible AI guardrail engine for agent tool validation."""
    pass


@cli.command()
def demo() -> None:
    """Run a demonstration of guardrail validation."""
    engine = build_responsible_ai_engine()
    engine.add_ruleset(build_booking_rules())
    engine.add_ruleset(build_data_access_rules())

    test_cases = [
        ("book_hotel", {"hotel": "Grand Plaza", "guests": 5, "nights": 3}),
        ("book_hotel", {"hotel": "Grand Plaza", "guests": 15, "nights": 3}),
        ("book_hotel", {"hotel": "Grand Plaza", "guests": 2, "nights": 45}),
        ("query_data", {"query": "SELECT name FROM users", "limit": 100}),
        ("query_data", {"query": "SELECT * FROM users", "limit": 5000}),
        ("delete_all", {"target": "users"}),
        (
            "book_hotel",
            {"hotel": "Grand Plaza", "guests": 2, "notes": "filter by race"},
        ),
    ]

    for tool_name, tool_input in test_cases:
        result = engine.validate(tool_name, tool_input)
        status = "ALLOWED" if result.allowed else "BLOCKED"
        click.echo(f"\n{status}: {tool_name}({tool_input})")
        for violation in result.violations:
            click.echo(f"  - {violation}")

    click.echo(f"\nAudit log: {len(engine.audit_log)} entries")


@cli.command()
def pillars() -> None:
    """List the AWS Responsible AI framework pillars."""
    responsible_ai_pillars = [
        ("Fairness", "Equitable treatment across demographic groups"),
        ("Explainability", "Understandable model decisions and outputs"),
        ("Privacy & Security", "Protection of sensitive data and PII"),
        ("Transparency", "Clear disclosure of AI system capabilities and limits"),
        ("Veracity & Robustness", "Accurate and reliable model outputs"),
        ("Safety", "Prevention of harmful outcomes"),
        ("Controllability", "Human oversight and intervention capability"),
        ("Governance", "Organizational policies and accountability structures"),
    ]
    for index, (pillar_name, pillar_description) in enumerate(
        responsible_ai_pillars, 1
    ):
        click.echo(f"  {index}. {pillar_name:<25} {pillar_description}")


if __name__ == "__main__":
    cli()
