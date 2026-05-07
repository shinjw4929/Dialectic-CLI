import contextlib
import io
import unittest


from src.dev_skill_cli import SKILLS, build_prompt, list_skills, main


class DevSkillCliTest(unittest.TestCase):
    def test_list_skills_includes_known_workflows(self) -> None:
        output = list_skills()

        self.assertIn("create-plan", output)
        self.assertIn("sync-docs", output)
        self.assertIn("review-code", output)

    def test_build_prompt_uses_native_codex_skill(self) -> None:
        sync_docs = next(skill for skill in SKILLS if skill.name == "sync-docs")
        output = build_prompt(sync_docs, None)

        self.assertTrue(output.startswith("$sync-docs\n"))
        self.assertIn(".claude/skills/sync-docs/SKILL.md", output)
        self.assertIn("`sync-docs` 실행해줘.", output)

    def test_main_rejects_unknown_workflow(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            exit_code = main(["missing-skill"])

        self.assertNotEqual(exit_code, 0)
        self.assertIn("unknown workflow", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
