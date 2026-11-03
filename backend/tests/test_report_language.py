from unittest.mock import Mock
import pytest
from app.utils.locale import set_locale
from app.utils.report_language import ensure_report_language
from app.utils.interview_prompt import optimize_interview_prompt

@pytest.fixture(autouse=True)
def english():
    set_locale("en")
    yield
    set_locale("en")

def test_english_report_makes_no_extra_model_request():
    llm=Mock()
    assert ensure_report_language("Evidence is incomplete.",llm) == "Evidence is incomplete."
    llm.chat.assert_not_called()

def test_chinese_quote_is_translated_and_labelled():
    llm=Mock()
    llm.chat.return_value='Buyer: "Evidence is required."'
    result=ensure_report_language("Buyer: 需要证据",llm)
    assert "translated into English" in result
    assert 'Buyer: "Evidence is required."' in result
    assert llm.chat.call_count == 1

@pytest.mark.parametrize("answer", ["仍然是中文", "", None])
def test_invalid_repair_fails_instead_of_completing(answer):
    llm=Mock()
    llm.chat.return_value=answer
    with pytest.raises(ValueError,match="language validation failed"):
        ensure_report_language("需要证据",llm)
    assert llm.chat.call_count == 1

def test_selected_chinese_is_not_forced_to_english():
    set_locale("zh")
    llm=Mock()
    assert ensure_report_language("需要证据",llm) == "需要证据"
    llm.chat.assert_not_called()

def test_report_and_interactive_paths_share_language_contract():
    from app.api.simulation import optimize_interview_prompt as api_prompt
    from app.services.zep_tools import optimize_interview_prompt as report_prompt
    assert api_prompt is report_prompt is optimize_interview_prompt
    assert "English" in report_prompt("What evidence would you require?")
    assert report_prompt(report_prompt("Question")) == report_prompt("Question")
