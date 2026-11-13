import importlib.util
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
PLAN_SPEC = importlib.util.spec_from_file_location("merge_plan", HERE / "merge_plan.py")
merge = importlib.util.module_from_spec(PLAN_SPEC)
PLAN_SPEC.loader.exec_module(merge)
APPLY_SPEC = importlib.util.spec_from_file_location("merge_apply", HERE / "merge_apply.py")
apply_mod = importlib.util.module_from_spec(APPLY_SPEC)
APPLY_SPEC.loader.exec_module(apply_mod)


def card(card_id, root_id, content, version=3):
    return {"id": card_id, "root_id": root_id, "content": content, "grammar_version": version}


SOURCE = {
    "id": "mkjd_s", "name": "源",
    "chapters": [{"id": "ch_s", "name": "章节", "cards": [
        card("c1", "r1", "同一张卡"),
        card("c2", "r2", "同一张卡"),
        card("c3", "r3", "另一张"),
    ]}],
}
TARGET = {"id": "mkjd_t", "name": "目标", "chapters": [{"id": "ch_t", "name": "目标章", "cards": []}]}


class MergeApplyTests(unittest.TestCase):
    def test_duplicate_plan_requires_explicit_policy(self):
        plan = merge.analyze([SOURCE], TARGET)
        args = Namespace(skip_duplicates=False, sample=False)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            apply_mod._need_decision(plan, args)

    def test_skip_duplicates_keeps_first_content_hash(self):
        plan = merge.analyze([SOURCE], TARGET)
        args = Namespace(skip_duplicates=True, sample=False)
        chosen = apply_mod._choose_cards(plan, args)
        self.assertEqual([item["source_card_id"] for item in chosen], ["c1", "c3"])

    def test_dry_run_does_not_write(self):
        plan = merge.analyze([SOURCE], TARGET)
        args = Namespace(skip_duplicates=True, sample=False, apply=False, allow_upload=False)
        target_tree = {"id": "mkjd_t", "name": "目标", "chapters": [
            {"id": "ch_t", "name": "目标章", "cards": []},
        ]}
        with patch.object(apply_mod, "_find_deck", return_value={"id": "mkjd_t", "name": "目标"}), \
             patch.object(apply_mod, "fetch_deck_tree", return_value=target_tree), \
             patch.object(apply_mod, "_create_chapter") as create_chapter, \
             patch.object(apply_mod, "_create_card") as create_card:
            result = apply_mod.apply_plan(plan, args, "token")
        self.assertTrue(result["dry_run"])
        self.assertEqual(len(result["created"]), 2)
        create_chapter.assert_not_called()
        create_card.assert_not_called()

    def test_sample_selects_one_card(self):
        plan = merge.analyze([SOURCE], TARGET)
        args = Namespace(skip_duplicates=False, sample=True)
        chosen = apply_mod._choose_cards(plan, args)
        self.assertEqual(len(chosen), 1)
        self.assertEqual(chosen[0]["source_card_id"], "c1")


if __name__ == "__main__":
    unittest.main()
