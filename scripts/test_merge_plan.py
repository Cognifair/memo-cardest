import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "merge_plan.py"
SPEC = importlib.util.spec_from_file_location("merge_plan", SCRIPT)
merge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(merge)


def card(card_id, root_id, content, version=3):
    return {"id": card_id, "root_id": root_id, "content": content, "grammar_version": version}


SOURCE_A = {
    "id": "mkjd_a", "name": "源 A",
    "chapters": [{"id": "ch_a1", "name": "相同章节", "cards": [
        card("card_a1", "root_a1", "问题 A\n---\n答案 [Card#ID/root_a2#下一张]"),
        card("card_a2", "root_a2", "问题 A2\n---\n答案 [Card#ID/root_ext#外部]"),
    ]}],
}
SOURCE_B = {
    "id": "mkjd_b", "name": "源 B",
    "chapters": [{"id": "ch_b1", "name": "相同章节", "cards": [
        card("card_b1", "root_b1", "问题 A\n---\n答案 [Card#ID/root_a2#下一张]"),
        card("card_b2", "root_b2", "图片 ![x](https://example.test/a.png)\n---\n音频 [Audio#abc]"),
    ]}, {"id": "ch_empty", "name": "空章", "cards": []}],
}
TARGET = {"id": "mkjd_t", "name": "目标", "chapters": [{"id": "ch_t1", "name": "相同章节", "cards": []}]}


class MergePlanTests(unittest.TestCase):
    def test_parse_references(self):
        text = "x [Card#ID/root_a#标签] y [Card#ID/root.b#另一个]"
        self.assertEqual(merge.parse_references(text), ["root_a", "root.b"])
        self.assertEqual(merge.parse_references("没有引用"), [])

    def test_media_detection(self):
        self.assertEqual(merge.media_kind("![x](a.png) [Audio#id]"), ["image", "audio"])

    def test_analyze_classifies_links_conflicts_media(self):
        plan = merge.analyze([SOURCE_A, SOURCE_B], TARGET)
        self.assertEqual(plan["counts"]["cards"], 4)
        self.assertEqual(plan["counts"]["chapters"], 3)
        self.assertEqual(len(plan["conflicts"]["duplicate_cards"]), 1)
        self.assertEqual(len(plan["conflicts"]["duplicate_chapters"]), 1)
        self.assertEqual(len(plan["conflicts"]["target_chapter_overlap"]), 1)
        self.assertEqual(len(plan["conflicts"]["empty_chapters"]), 1)
        self.assertEqual(len(plan["links"]["internal"]), 2)
        self.assertEqual(len(plan["links"]["outbound_external"]), 1)
        self.assertEqual(plan["links"]["inbound_scanned"], False)
        self.assertIn("duplicate_cards", plan["requires_decision"])
        self.assertIn("chapter_conflict", plan["requires_decision"])
        self.assertEqual(plan["media"]["image_ref_cards"], 1)
        self.assertEqual(plan["media"]["audio_ref_cards"], 1)
        self.assertTrue(any("外部入链" in warning for warning in plan["warnings"]))

    def test_inbound_links_are_reported_but_not_changed(self):
        inbound = [{
            "deck_id": "mkjd_other", "chapter_id": "ch_other", "card_id": "card_other",
            "root_id": "root_other", "references": ["root_a1"],
        }]
        plan = merge.analyze([SOURCE_A, SOURCE_B], TARGET, inbound_cards=inbound)
        self.assertEqual(plan["links"]["inbound_scanned"], True)
        self.assertEqual(len(plan["links"]["inbound_external"]), 1)
        self.assertTrue(any("删除源牌组" in warning for warning in plan["warnings"]))
        # Analyze is read-only: source data is untouched.
        self.assertEqual(SOURCE_A["chapters"][0]["cards"][0]["content"],
                         "问题 A\n---\n答案 [Card#ID/root_a2#下一张]")

    def test_plan_defaults_warn_when_inbound_not_scanned(self):
        plan = merge.analyze([SOURCE_A], TARGET)
        self.assertTrue(any("--scan-inbound" in warning for warning in plan["warnings"]))
        self.assertFalse(plan["links"]["inbound_scanned"])

    def test_preview_contains_safety_notice(self):
        plan = merge.analyze([SOURCE_A, SOURCE_B], TARGET)
        preview = merge._preview_markdown(plan)
        self.assertIn("没有写卡、移卡或删除", preview)
        self.assertIn("确认后再手动删除源牌组", preview)


if __name__ == "__main__":
    unittest.main()
