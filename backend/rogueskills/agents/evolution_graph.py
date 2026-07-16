from typing import Any, TypedDict

from rogueskills.contracts.runtime import EvaluationRequest, EvaluationResult, RuntimeExecution

from .ports import MutationPlanner, OutputEvaluator, RuntimeAdapter


class EvolutionGraphState(TypedDict, total=False):
    request: EvaluationRequest
    genome: dict[str, Any]
    runtime_case: dict[str, Any]
    scenario: dict[str, Any]
    execution: RuntimeExecution
    evaluation: EvaluationResult
    proposals: list[dict[str, Any]]


def build_evolution_graph(
    *,
    runtime: RuntimeAdapter,
    evaluator: OutputEvaluator,
    planner: MutationPlanner,
) -> Any:
    """Build the P1 runtime graph without coupling domain algorithms to LangGraph."""
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as error:
        raise RuntimeError(
            "Install RogueSkills with the 'agent' extra to use LangGraph."
        ) from error

    async def execute_runtime(state: EvolutionGraphState) -> dict[str, Any]:
        execution = await runtime.execute(state["request"], state["genome"], state["runtime_case"])
        return {"execution": execution}

    def evaluate_output(state: EvolutionGraphState) -> dict[str, Any]:
        result = evaluator.evaluate(state["request"], state["execution"], state["scenario"])
        return {"evaluation": result}

    async def propose_mutations(state: EvolutionGraphState) -> dict[str, Any]:
        proposals = await planner.propose(state["genome"], state["evaluation"])
        return {"proposals": [proposal.model_dump(mode="json") for proposal in proposals]}

    def route_after_evaluation(state: EvolutionGraphState) -> str:
        return "done" if state["evaluation"].passed else "propose"

    graph = StateGraph(EvolutionGraphState)
    graph.add_node("execute_runtime", execute_runtime)
    graph.add_node("evaluate_output", evaluate_output)
    graph.add_node("propose_mutations", propose_mutations)
    graph.add_edge(START, "execute_runtime")
    graph.add_edge("execute_runtime", "evaluate_output")
    graph.add_conditional_edges(
        "evaluate_output",
        route_after_evaluation,
        {"done": END, "propose": "propose_mutations"},
    )
    graph.add_edge("propose_mutations", END)
    return graph.compile()
