"""REPL kernel lifecycle: create/connect Jupyter kernels, capture output, shut down."""

from agenticpytools.kernel import client
from agenticpytools.kernel.content import capture

__all__ = ["capture", "client"]
