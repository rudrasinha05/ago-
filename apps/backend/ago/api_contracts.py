"""Typed request contracts shared by presentation adapters."""

from pydantic import BaseModel, ConfigDict


class StrictInput(BaseModel):
    # Preserve exact passwords and meaningful whitespace; reject authority injection.
    model_config = ConfigDict(extra="forbid")
