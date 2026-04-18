# server_side/graph/workflow.py
"""Main LangGraph workflow definition for email processing pipeline."""

from typing import Literal
import os

from langgraph.graph import StateGraph, END
from server_side.core.logger import logger
from server_side.database.models import EmailStatusEnum
from server_side.graph.state import EmailAgentState


def create_workflow(nodes: dict, save_image: bool = True):
    """Create the email processing workflow.

    Args:
        nodes: Dictionary of node functions
        save_image: Whether to save workflow architecture as an image

    Returns:
        Compiled StateGraph
    """
    # Initialize graph
    workflow = StateGraph(EmailAgentState)

    # Add all nodes
    workflow.add_node("email_retrieval", nodes["email_retrieval"])
    workflow.add_node("classification", nodes["classification"])
    workflow.add_node("context_analysis", nodes["context_analysis"])
    workflow.add_node("review_check", nodes["review_check"])
    workflow.add_node("response_generation", nodes["response_generation"])
    workflow.add_node("review_routing", nodes["review_routing"])
    workflow.add_node("human_review", nodes["human_review"])
    workflow.add_node("response_sending", nodes["response_sending"])
    workflow.add_node("followup_scheduling", nodes["followup_scheduling"])
    workflow.add_node("error_handler", nodes["error_handler"])

    # Define edges with conditional routing
    workflow.set_entry_point("email_retrieval")

    # Email retrieval → Classification
    workflow.add_edge("email_retrieval", "classification")

    # Classification → Skip/Review/Context/Error
    workflow.add_conditional_edges(
        "classification",
        lambda state: (
            "end_skipped"
            if state.get("skip_email")
            else "human_review"
            if state.get("needs_human_review")
            else "context_analysis"
            if not state.get("error_message")
            else "error_handler"
        ),
        {
            "end_skipped": END,
            "human_review": "human_review",
            "context_analysis": "context_analysis",
            "error_handler": "error_handler",
        },
    )

    # Context Analysis → Response Generation
    workflow.add_edge("context_analysis", "response_generation")

    # Response Generation → Review Routing or Response Sending
    def route_after_generation(state: EmailAgentState) -> Literal["human_review", "error_handler"]:
        if state.get("error_message"):
            return "error_handler"
        return "human_review"

    workflow.add_conditional_edges("response_generation", route_after_generation)

    # Human Review → Review Check (poll decision)
    workflow.add_edge("human_review", "review_check")

    # Review Check (awaiting decision) → End or Review Routing
    workflow.add_conditional_edges(
        "review_check",
        lambda state: "end_pause" if state.get("awaiting_review") else "review_routing",
        {
            "end_pause": END,
            "review_routing": "review_routing",
        },
    )

    # Review Routing → Response Sending or End
    workflow.add_conditional_edges(
        "review_routing",
        lambda state: "response_sending" if state.get("route_after_review") == "response_sending" else "end_after_review",
        {
            "response_sending": "response_sending",
            "end_after_review": END,
        },
    )

    # Response Sending → Follow-up or Error
    workflow.add_conditional_edges(
        "response_sending",
        lambda state: "followup_scheduling" if state.get("status") == EmailStatusEnum.RESPONDED else "error_handler",
    )

    # Follow-up Scheduling → End
    workflow.add_edge("followup_scheduling", END)

    # Error Handler → End
    workflow.add_edge("error_handler", END)

    # Compile the graph
    app = workflow.compile()
    logger.info("Email processing workflow created successfully")

    # Save workflow as image
    if save_image:
        try:
            # Ensure output folder exists
            output_dir = os.path.join("client_side", "static", "media")
            os.makedirs(output_dir, exist_ok=True)

            # File path for PNG
            output_path = os.path.join(output_dir, "email_workflow.png")

            compiled_graph = app.get_graph()
            if not hasattr(compiled_graph, "draw_mermaid_png"):
                raise RuntimeError("No supported graph renderer produced image output")

            image_bytes = compiled_graph.draw_mermaid_png()
            if not image_bytes:
                raise RuntimeError("No supported graph renderer produced image output")

            with open(output_path, "wb") as image_file:
                image_file.write(image_bytes)

            logger.info(f"Workflow architecture saved as {output_path}")
        except Exception as e:
            logger.error(f"Failed to save workflow image: {e}", exc_info=True)

    return app