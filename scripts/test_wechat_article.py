import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fetch_wechat_article.py"

HTML = """<!doctype html><html><head>
<meta property="og:title" content="测试文章">
</head><body>
<h1>测试文章</h1>
<div id="js_content">
<p>第一段：名词解释。</p>
<p><img data-src="https://mmbiz.qpic.cn/test/640?wx_fmt=jpeg" data-w="640" data-ratio="0.75"></p>
<p>第二段：<a href="http://mp.weixin.qq.com/s?__biz=abc">子文章</a>。</p>
</div>
<script>var nickname = "测试公众号";</script>
</body></html>"""


class WeChatArticleTests(unittest.TestCase):
    def test_extracts_text_images_and_sub_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "article.html"
            out = Path(tmp) / "source"
            source.write_text(HTML, encoding="utf-8")
            result = subprocess.run([sys.executable, "-B", str(SCRIPT),
                                     "--html-file", str(source), "--out", str(out)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["title"], "测试文章")
            self.assertEqual(manifest["images"][0]["url"], "https://mmbiz.qpic.cn/test/640?wx_fmt=jpeg")
            self.assertEqual(manifest["sub_links"][0]["url"], "http://mp.weixin.qq.com/s?__biz=abc")
            self.assertIn("第一段", (out / "article.md").read_text(encoding="utf-8"))
            self.assertEqual(manifest["images"][0]["decision"], "needs_review")


if __name__ == "__main__":
    unittest.main()
