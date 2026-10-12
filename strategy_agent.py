
"""CrewAI research agent for reviewing deterministic trading signals.

Research only: this module does not access brokerage tools or place orders.
"""

import json
import os

from crewai import Agent, Crew, Process, Task


def build_strategy_crew() -> Crew:
    """Build a research crew using the configured LLM provider."""

    agent = Agent(
        role="Trading Strategy Research Analyst",
        goal=(
            "Explain a deterministic trading signal using only the supplied "
            "indicator evidence. Identify risks and uncertainty."
        ),
        backstory=(
            "You are a cautious quantitative research analyst. You do not "
            "invent market data, change the supplied signal, promise profits, "
            "or recommend placing an order."
        ),
        verbose=False,
        allow_delegation=False,
    )

    task = Task(
        description=(
            "Review this deterministic strategy result:\n{signal_json}\n\n"
            "Return a concise research report with:\n"
            "1. Ticker and supplied signal\n"
            "2. Indicator evidence supporting or weakening the signal\n"
            "3. Risk flags and missing information\n"
            "4. A reminder that this is not an order or a profit guarantee\n\n"
            "Use only the supplied information. If evidence is missing, say so. "
            "Do not invent prices, dates, news, or indicators. Do not change "
            "BUY, SELL, or HOLD; report the supplied signal faithfully."
        ),
        expected_output=(
            "A concise research report containing the ticker, original signal, "
            "evidence, risks, missing information, and limitations."
        ),
        agent=agent,
    )

    return Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )


def review_signal(signal_result: dict) -> str:
    """Ask the configured LLM to review a deterministic signal."""
    if not isinstance(signal_result, dict):
        raise TypeError("signal_result must be a dictionary")

    if signal_result.get("signal") not in {"BUY", "SELL", "HOLD"}:
        raise ValueError("signal_result must contain BUY, SELL, or HOLD")

    # Avoid sending arbitrary oversized payloads to the model.
    signal_json = json.dumps(signal_result, allow_nan=False)
    if len(signal_json) > 12000:
        raise ValueError("Signal payload is too large")

    if not os.getenv("OPENAI_API_KEY"):
        raise EnvironmentError(
            "OPENAI_API_KEY is not set. Configure your model-provider key "
            "locally before running the LLM review."
        )

    crew = build_strategy_crew()
    result = crew.kickoff(inputs={"signal_json": signal_json})
    return str(result)


if __name__ == "__main__":
    print(
        "Strategy research agent is defined. Import review_signal() and pass "
        "a result from trading_strategy.generate_signal()."
    )
