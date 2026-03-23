from app.services.prompt_service import PromptService
from app.services.llm import SECTION_SYSTEM_PROMPTS
from app.prompts.templates import SYSTEM_ORACLE


def test_section_system_prompt_mapping_has_fallbacks():
    """Verify the hardcoded mapping still exists as fallback."""
    assert "pre_call" in SECTION_SYSTEM_PROMPTS
    assert "post_call" in SECTION_SYSTEM_PROMPTS
    assert SECTION_SYSTEM_PROMPTS["pre_call"] != ""


def test_prompt_service_section_key_mapping():
    """Verify the section-to-prompt-id mapping covers all sections."""
    from app.services.prompt_service import SECTION_TO_PROMPT_ID
    for section in ["pre_call", "post_call", "follow_up", "tal", "se_poc_plan", "se_arch_fit", "se_competitor"]:
        assert section in SECTION_TO_PROMPT_ID, f"Missing mapping for section: {section}"
