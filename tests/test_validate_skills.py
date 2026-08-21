"""Tests for scripts/validate_skills.py — the collection's own structural gate.

Every check gets both directions: a shape it must refuse, and one it must let
through. A validator with only passing fixtures is the rubber stamp its own
`drift-to-gate` skill names.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from support import load_repo_script, run_repo_script

script = load_repo_script("validate_skills.py")

FRONTMATTER = """---
name: {name}
description: {description}
roles: [{roles}]
{gate}
---

# Title

## A section

Body text.
"""


def skill_text(name: str = "demo", description: str = "Use when demoing.",
               roles: str = "implement", gate: str = "gate: none\ngate_reason: nothing to refuse",
               body: str = "") -> str:
    return FRONTMATTER.format(name=name, description=description, roles=roles, gate=gate) + body


class CheckTest(unittest.TestCase):
    def setUp(self) -> None:
        script.errors.clear()
        script.warnings.clear()

    def codes(self) -> list[str]:
        return sorted(e.split(":", 1)[0] for e in script.errors)

    def warn_codes(self) -> list[str]:
        return sorted(w.split(":", 1)[0] for w in script.warnings)

    def check(self, text: str, *, name: str = "demo", scripts: set[str] | None = None) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / name
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(text, encoding="utf-8")
            script.check_skill(skill_dir, {name}, scripts if scripts is not None else set())
        return self.codes()


class RolesTest(CheckTest):
    def test_valid_roles_pass(self) -> None:
        self.assertEqual(self.check(skill_text(roles="implement, review")), [])

    def test_missing_roles_is_e7(self) -> None:
        text = skill_text().replace("roles: [implement]\n", "")
        self.assertIn("E7", self.check(text))

    def test_empty_roles_is_e7(self) -> None:
        self.assertIn("E7", self.check(skill_text(roles="")))

    def test_unknown_role_is_e7(self) -> None:
        self.assertIn("E7", self.check(skill_text(roles="implement, deploy")))

    def test_each_unknown_role_is_reported(self) -> None:
        self.check(skill_text(roles="deploy, publish"))
        self.assertEqual(self.codes().count("E7"), 2)


class GateTest(CheckTest):
    def test_named_gate_resolving_to_a_script_passes(self) -> None:
        self.assertEqual(
            self.check(skill_text(gate="gate: rfc-index"), scripts={"rfc-index"}), []
        )

    def test_named_gate_with_no_script_is_e14(self) -> None:
        self.assertIn("E14", self.check(skill_text(gate="gate: imaginary"), scripts={"rfc-index"}))

    def test_missing_gate_is_e14(self) -> None:
        text = skill_text().replace("gate: none\ngate_reason: nothing to refuse\n", "")
        self.assertIn("E14", self.check(text))

    def test_none_without_reason_is_e14(self) -> None:
        self.assertIn("E14", self.check(skill_text(gate="gate: none")))

    def test_none_with_blank_reason_is_e14(self) -> None:
        self.assertIn("E14", self.check(skill_text(gate="gate: none\ngate_reason:   ")))

    def test_named_gate_with_a_reason_is_e14(self) -> None:
        # Both filled means one of them is stale; the reason only applies to none.
        codes = self.check(skill_text(gate="gate: rfc-index\ngate_reason: because"),
                           scripts={"rfc-index"})
        self.assertIn("E14", codes)


class DescriptionTest(CheckTest):
    def test_three_hundred_chars_passes(self) -> None:
        self.assertEqual(self.check(skill_text(description="U" * 300)), [])

    def test_over_budget_is_e5(self) -> None:
        self.assertIn("E5", self.check(skill_text(description="U" * 301)))

    def test_the_old_format_ceiling_no_longer_passes(self) -> None:
        # 1024 is what the Agent Skills format allows; the collection's own
        # budget is tighter, and this is the regression that proves it moved.
        self.assertIn("E5", self.check(skill_text(description="U" * 1024)))


class TriggerSectionTest(CheckTest):
    def test_use_this_skill_when_is_e15(self) -> None:
        self.assertIn("E15", self.check(skill_text(body="\n## Use this skill when\n\n- Always.\n")))

    def test_do_not_use_this_skill_when_is_e15(self) -> None:
        self.assertIn("E15", self.check(skill_text(body="\n## Do not use this skill when\n\n- Never.\n")))

    def test_use_when_without_this_skill_is_e15(self) -> None:
        self.assertIn("E15", self.check(skill_text(body="\n## Use when\n\nText.\n")))

    def test_a_section_merely_containing_the_word_when_passes(self) -> None:
        self.assertEqual(self.check(skill_text(body="\n## What to do when a gate refuses\n\nText.\n")), [])

    def test_matching_is_case_insensitive(self) -> None:
        self.assertIn("E15", self.check(skill_text(body="\n## USE THIS SKILL WHEN\n\nText.\n")))


class BodyBudgetTest(CheckTest):
    def test_a_short_body_warns_nothing(self) -> None:
        self.check(skill_text())
        self.assertEqual(self.warn_codes(), [])

    def test_an_oversize_body_is_w1_and_not_an_error(self) -> None:
        fat = "\n" + ("word " * (script.MAX_BODY_TOKENS * script.CHARS_PER_TOKEN) + "\n")
        self.assertEqual(self.check(skill_text(body=fat)), [])
        self.assertIn("W1", self.warn_codes())


class BundledGatesTest(unittest.TestCase):
    def test_gate_names_are_kebab_cased_script_stems(self) -> None:
        names = script.bundled_gates()
        self.assertIn("rfc-index", names)
        self.assertIn("check-commit-msg", names)
        self.assertNotIn("rfc_index", names)

    def test_repo_scripts_are_claimable_too(self) -> None:
        self.assertIn("validate-skills", script.bundled_gates())


class CollectionTest(unittest.TestCase):
    def test_the_real_collection_passes(self) -> None:
        proc = run_repo_script("validate_skills.py", timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


class BrokenLinkTest(unittest.TestCase):
    """E9 covers every .md in a skill, not only SKILL.md."""

    def links(self, text: str, *, existing: list[str] = ()) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "skills" / "demo" / "references").mkdir(parents=True)
            for name in existing:
                target = repo / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("x\n", encoding="utf-8")
            page = repo / "skills" / "demo" / "references" / "page.md"
            page.write_text(text, encoding="utf-8")
            return script.broken_links(page, repo)

    def test_a_resolving_sibling_link_is_clean(self) -> None:
        self.assertEqual(
            self.links("See [other](other.md).",
                       existing=["skills/demo/references/other.md"]), [])

    def test_a_missing_target_is_reported(self) -> None:
        self.assertEqual(self.links("See [other](other.md)."), ["other.md"])

    def test_a_skill_relative_path_inside_references_is_reported(self) -> None:
        # The bug this exists for: a section moved out of SKILL.md keeps its
        # `references/x.md` link, which from inside references/ resolves to
        # references/references/x.md.
        self.assertEqual(
            self.links("See [x](references/other.md).",
                       existing=["skills/demo/references/other.md"]),
            ["references/other.md"])

    def test_a_repo_root_relative_path_resolves(self) -> None:
        self.assertEqual(self.links("[readme](README.md)", existing=["README.md"]), [])

    def test_external_urls_are_not_checked(self) -> None:
        self.assertEqual(self.links("[a](https://example.invalid/x) [b](mailto:a@b.c)"), [])

    def test_a_bare_anchor_is_not_checked(self) -> None:
        self.assertEqual(self.links("[above](#section)"), [])

    def test_a_shell_variable_target_is_not_checked(self) -> None:
        self.assertEqual(self.links("[comment]($URL)"), [])

    def test_link_shaped_text_in_inline_code_is_not_a_link(self) -> None:
        self.assertEqual(self.links("a dispatch table: `handlers[kind](payload)`"), [])

    def test_link_shaped_text_in_a_fenced_block_is_not_a_link(self) -> None:
        self.assertEqual(
            self.links("```markdown\n| [0001](0001-kebab-title.md) | Title |\n```\n"), [])

    def test_an_anchor_on_a_real_file_resolves_to_the_file(self) -> None:
        self.assertEqual(
            self.links("[x](other.md#part)",
                       existing=["skills/demo/references/other.md"]), [])

    def test_every_shipped_skill_page_resolves(self) -> None:
        repo = Path(script.__file__).resolve().parent.parent
        for page in sorted((repo / "skills").rglob("*.md")):
            with self.subTest(page=str(page.relative_to(repo))):
                self.assertEqual(script.broken_links(page, repo), [])


if __name__ == "__main__":
    unittest.main()
