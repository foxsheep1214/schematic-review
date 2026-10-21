"""The review is kept twice: 审查报告.md and 审查报告.html built from it, so pictures show inline in a browser."""
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from report_html import to_html
import pack_review


SAMPLE = '\n'.join([
    '# 审查报告：板 A', '', '## 结论', '', '不能定稿：1 处 **电路错误**，见 `F1`。', '',
    '| 项目 | 数量 |', '|---|---|', '| 错误 | 1 |', '',
    '### F1　TVS 单级', '', '- **根因**：钳位高于 <6.5 V> & 无限流', '- **怎么改**：见 [记录](record/review-results.json)', '',
    '![现状电路](record/evidence/figures/F1-actual.png)', '', '图：现状。现状电路', '',
    '1. 先改 F1', '2. 再复审', '',
    '<details>', '<summary>展开</summary>', '', '- 细节', '</details>', ''])


class ToHtmlTests(unittest.TestCase):
    def setUp(self):
        self.html = to_html(SAMPLE)

    def test_a_standalone_page_titled_after_the_first_heading(self):
        self.assertTrue(self.html.startswith('<!doctype html>'))
        self.assertIn('<meta charset="utf-8">', self.html)
        self.assertIn('<title>审查报告：板 A</title>', self.html)
        self.assertIn('prefers-color-scheme: dark', self.html)

    def test_headings_lists_tables_and_inline_marks(self):
        h = self.html
        self.assertIn('<h2>结论</h2>', h)
        self.assertIn('<h3>F1　TVS 单级</h3>', h)
        self.assertIn('<strong>电路错误</strong>', h)
        self.assertIn('<code>F1</code>', h)
        self.assertIn('<th>项目</th><th>数量</th>', h)
        self.assertIn('<td>错误</td><td>1</td>', h)
        self.assertIn('<li><strong>根因</strong>：钳位高于 &lt;6.5 V&gt; &amp; 无限流</li>', h)
        self.assertIn('<a href="record/review-results.json">记录</a>', h)
        self.assertIn('<ol>\n<li>先改 F1</li>\n<li>再复审</li>\n</ol>', h)

    def test_figures_show_inline_and_details_stay_foldable(self):
        self.assertIn('<figure><img src="record/evidence/figures/F1-actual.png" alt="现状电路"></figure>', self.html)
        self.assertIn('<details>\n<summary>展开</summary>', self.html)
        self.assertIn('<li>细节</li>', self.html)


    def test_a_pipe_line_without_a_separator_row_is_a_paragraph_not_a_hang(self):
        html = to_html('# T\n\n| a | b\n下一行\n')
        self.assertIn('<p>| a | b<br>\n下一行</p>', html)

    def test_an_image_path_may_hold_a_space_and_the_alt_a_bracket(self):
        html = to_html('![x](record/evidence/figures/a b.png)\n')
        self.assertIn('<img src="record/evidence/figures/a b.png" alt="x">', html)


class PackTests(unittest.TestCase):
    def test_pack_wants_the_html_copy_built_from_the_current_markdown(self):
        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d)
            (out / pack_review.REPORT).write_text(SAMPLE, encoding='utf-8')
            errors, _ = pack_review.pack(out, {'review-results.json': str(out / 'absent.json')}, None, {})
            self.assertTrue(any(pack_review.REPORT_HTML in e for e in errors), errors)
            (out / pack_review.REPORT_HTML).write_text('<p>edited by hand</p>', encoding='utf-8')
            errors, _ = pack_review.pack(out, {'review-results.json': str(out / 'absent.json')}, None, {})
            self.assertTrue(any('re-render' in e for e in errors), errors)
            (out / pack_review.REPORT_HTML).write_text(to_html(SAMPLE), encoding='utf-8')
            errors, _ = pack_review.pack(out, {'review-results.json': str(out / 'absent.json')}, None, {})
            self.assertFalse(any(pack_review.REPORT_HTML in e for e in errors), errors)


if __name__ == '__main__':
    unittest.main()
