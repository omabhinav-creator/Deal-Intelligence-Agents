from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from Hindsight.ai.deal_brief import DealBriefGenerator
from Hindsight.ai.deal_autopsy import DealAutopsyAnalyzer
from Hindsight.ai.deal_changes import DealChangeAnalyzer
from Hindsight.ai.similar_deals import SimilarDealsFinder


@pytest.mark.parametrize(
    ("module_name", "generator_type"),
    [
        ("Hindsight.ai.deal_brief", DealBriefGenerator),
        ("Hindsight.ai.deal_autopsy", DealAutopsyAnalyzer),
        ("Hindsight.ai.deal_changes", DealChangeAnalyzer),
        ("Hindsight.ai.similar_deals", SimilarDealsFinder),
    ],
)
def test_groq_feature_clients_disable_sdk_automatic_retries(
    monkeypatch,
    module_name: str,
    generator_type,
):
    calls = []

    def groq_factory(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(f"{module_name}.Groq", groq_factory)
    generator = generator_type(memory_client=Mock())
    generator._groq_api_key = "unit-test-key"

    generator._get_groq_client()

    assert calls == [{"api_key": "unit-test-key", "max_retries": 0}]
