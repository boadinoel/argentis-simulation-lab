"""Separate Camel context budgeting from the provider's reply-token cap."""
from camel.models import OpenAIModel


class LabOpenAIModel(OpenAIModel):
    @property
    def token_limit(self):
        # Camel's base implementation returns max_tokens here, conflating the
        # output cap with memory capacity. Keep a conservative independent limit.
        return 32768
