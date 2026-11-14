"""Separate Camel context budgeting from the provider's reply-token cap."""
from camel.models import OpenAIModel
from modern_openai import ResponsesBridge, is_modern


class LabOpenAIModel(OpenAIModel):
    def __init__(self, *args, receipt_path=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._responses_bridge = ResponsesBridge(receipt_path)

    def _run(self, messages, response_format=None, tools=None):
        if not is_modern(self.model_type):
            return super()._run(messages,response_format,tools)
        request=self._responses_bridge.request(self.model_type,messages,self.model_config_dict,tools,response_format)
        return self._responses_bridge.completion(self._client.responses.create(**request),self.model_type)

    async def _arun(self, messages, response_format=None, tools=None):
        if not is_modern(self.model_type):
            return await super()._arun(messages,response_format,tools)
        request=self._responses_bridge.request(self.model_type,messages,self.model_config_dict,tools,response_format)
        response=await self._async_client.responses.create(**request)
        return self._responses_bridge.completion(response,self.model_type)

    @property
    def token_limit(self):
        # Camel's base implementation returns max_tokens here, conflating the
        # output cap with memory capacity. Keep a conservative independent limit.
        return 32768
