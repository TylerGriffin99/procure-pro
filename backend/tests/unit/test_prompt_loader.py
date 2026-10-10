import pytest

from app.harness.prompts import PLAYBOOKS_DIR, PROMPTS_DIR, load_playbook, load_prompt


def test_load_prompt_reads_named_markdown():
    text = load_prompt("categorise_wbs")
    assert text == (PROMPTS_DIR / "categorise_wbs.md").read_text()
    assert text.strip()


def test_load_prompt_missing_names_the_path():
    with pytest.raises(FileNotFoundError, match="does_not_exist.md"):
        load_prompt("does_not_exist")


def test_load_playbook_reads_format_file():
    assert load_playbook("generic") == (PLAYBOOKS_DIR / "generic.md").read_text()


def test_load_playbook_missing_raises():
    with pytest.raises(FileNotFoundError, match="nope.md"):
        load_playbook("nope")


def test_jev_instruction_prompts_have_none_option_placeholder():
    assert "{none_option}" in load_prompt("jev_wbs_instructions")
    assert "{none_option}" in load_prompt("jev_vps_instructions")
