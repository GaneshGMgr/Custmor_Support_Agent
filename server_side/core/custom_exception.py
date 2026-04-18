"""Custom exception hierarchy for the customer support agent."""

import sys
import traceback
from typing import Any, Dict, Optional


class CustomerSupportException(Exception):
    """Base exception for customer support agent."""

    def __init__(
        self,
        message: str,
        error_details: Optional[object] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        self.context = context or {}
        self.message = message

        exc_type = exc_value = exc_tb = None
        if error_details is None:
            exc_type, exc_value, exc_tb = sys.exc_info()
        elif isinstance(error_details, BaseException):
            exc_type = type(error_details)
            exc_value = error_details
            exc_tb = error_details.__traceback__
        else:
            exc_type, exc_value, exc_tb = sys.exc_info()

        last_tb = exc_tb
        while last_tb and last_tb.tb_next:
            last_tb = last_tb.tb_next

        self.file_name = last_tb.tb_frame.f_code.co_filename if last_tb else "<unknown>"
        self.lineno = last_tb.tb_lineno if last_tb else -1
        self.traceback_str = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb)) if exc_type else ""

        super().__init__(self.__str__())

    def __str__(self):
        base = f"[{self.file_name}:{self.lineno}] {self.message}"
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            base += f" | Context: {context_str}"
        if self.traceback_str:
            return f"{base}\nTraceback:\n{self.traceback_str}"
        return base

class ConfigMissingException(CustomerSupportException):
    """Raised when a required configuration (.yaml/.env) is missing."""
    error_code = "CFG_001"
    status_code = 500

    def __init__(self, message: str, config_name: Optional[str] = None, error_details: Optional[object] = None):
        context = {"error_code": self.error_code, "config_name": config_name}
        super().__init__(message, error_details=error_details, context=context)

class ModelLoadException(CustomerSupportException):
    """Raised when a model cannot be loaded."""
    error_code = "MLD_001"
    status_code = 500

    def __init__(self, message: str, model_name: Optional[str] = None, error_details: Optional[object] = None):
        context = {"error_code": self.error_code, "model_name": model_name}
        super().__init__(message, error_details=error_details, context=context)

class LLMAPIDownException(CustomerSupportException):
    """Raised when remote LLM API is down/unreachable."""
    error_code = "LLM_001"
    status_code = 503

    def __init__(self, message: str, model_name: Optional[str] = None, error_details: Optional[object] = None):
        context = {"error_code": self.error_code, "model_name": model_name}
        super().__init__(message, error_details=error_details, context=context)
