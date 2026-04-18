# server_side\nodes\factory.py
"""Node factory - collects and exports all workflow nodes."""

from server_side.nodes.email_retrieval import email_retrieval_node
from server_side.nodes.classification import classification_node
from server_side.nodes.context_analysis import context_analysis_node
from server_side.nodes.review_check import review_check_node
from server_side.nodes.response_generation import response_generation_node
from server_side.nodes.review_routing import review_routing_node
from server_side.nodes.human_review import human_review_node
from server_side.nodes.response_sending import response_sending_node
from server_side.nodes.followup_scheduling import followup_scheduling_node
from server_side.nodes.error_handler import error_handler_node


def get_all_nodes() -> dict:
    """Get all node functions for workflow.

    Returns:
        Dictionary of node_name: node_function
    """
    return {
        "email_retrieval": email_retrieval_node,
        "classification": classification_node,
        "context_analysis": context_analysis_node,
        "review_check": review_check_node,
        "response_generation": response_generation_node,
        "review_routing": review_routing_node,
        "human_review": human_review_node,
        "response_sending": response_sending_node,
        "followup_scheduling": followup_scheduling_node,
        "error_handler": error_handler_node,
    }
