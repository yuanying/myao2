"""Jinja2 template utilities for LLM components."""

from jinja2 import Environment, PackageLoader, select_autoescape


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
