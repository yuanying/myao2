"""Jinja2 template utilities for LLM components."""

from datetime import datetime

from jinja2 import Environment, PackageLoader, select_autoescape


def format_timestamp(timestamp: datetime) -> str:
    """Format datetime to readable string.

    Args:
        timestamp: datetime object.

    Returns:
        Formatted string in YYYY-MM-DD HH:MM:SS format.
    """
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")


def create_jinja_env() -> Environment:
    """Create Jinja2 environment for LLM templates.

    Creates a configured Jinja2 environment that loads templates from
    the myao2.infrastructure.llm.templates package.

    Returns:
        Configured Jinja2 environment.
    """
    return Environment(
        loader=PackageLoader("myao2.infrastructure.llm", "templates"),
        autoescape=select_autoescape(),
        trim_blocks=True,
        lstrip_blocks=True,
    )
