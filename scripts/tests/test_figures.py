"""A P0/P1 defect and a proposed circuit change are shown, not only told: the actual circuit, and the
reference or changed circuit when the fix changes topology; the report leads with the root cause and the harm."""
import copy
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from validate_review import validate_review
from test_remediation import actionable
from test_validate_review import gap_with_task, proposed_option, fail, fixture
from validate_remediation import validate_figures
from render_report import render
from report_html import to_html
from review_quality import finding_wording


def figure(kind='ACTUAL', source='figures/F1-actual.png', caption='每条线只有一颗 TVS，直接接到 U1'):
    return {'kind': kind, 'source': source, 'locator': '原理图 p1，J1 与 R1 区域', 'caption': caption}


class ValidateFiguresTests(unittest.TestCase):
    def test_each_figure_names_kind_image_locator_and_caption(self):
        self.assertEqual([], validate_figures('F1', [figure()]))
        for bad in ({'kind': 'PHOTO'}, {'source': 'figures/F1.pdf'}, {'locator': ''}, {'caption': ' '}):
            with self.subTest(bad=bad):
                self.assertTrue(validate_figures('F1', [dict(figure(), **bad)]))

    def test_a_figure_source_is_a_safe_relative_path_without_spaces(self):
        for bad in ('figures/F1 actual.png', '../figures/F1.png', '/tmp/F1.png', 'figures/../../F1.png'):
            with self.subTest(bad=bad):
                self.assertTrue(validate_figures('F1', [figure(source=bad)]), bad)

    def test_the_actual_circuit_is_required(self):
        self.assertTrue(any('ACTUAL' in e for e in validate_figures('F1', None)))
        self.assertTrue(any('ACTUAL' in e for e in validate_figures('F1', [figure('REFERENCE', 'figures/ref.png')])))

    def test_a_topology_change_also_shows_the_changed_or_reference_circuit(self):
        errors = validate_figures('F1', [figure()], need_after=True)
        self.assertTrue(any('AFTER' in e and 'REFERENCE' in e for e in errors), errors)
        self.assertEqual([], validate_figures('F1', [figure(), figure('AFTER', 'figures/F1-after.png')], need_after=True))
        self.assertEqual([], validate_figures('F1', [figure(), figure('REFERENCE', 'figures/F1-ref.svg')], need_after=True))


class DefectFigureTests(unittest.TestCase):
    def test_a_p1_defect_without_figures_is_refused_when_actionable(self):
        p, r, db = actionable()
        r['findings'][0].pop('figures', None)
        out = validate_review(p, r, db, require_actionable=True)
        self.assertFalse(out['valid'])
        self.assertTrue(any('F1' in e and 'figures' in e for e in out['errors']), out['errors'])

    def test_an_assembly_fix_needs_only_the_actual_circuit(self):
        p, r, db = actionable()
        r['findings'][0]['figures'] = [figure()]
        out = validate_review(p, r, db, require_actionable=True)
        self.assertTrue(out['valid'], out['errors'])

    def test_a_component_fix_also_needs_the_changed_circuit(self):
        p, r, db = actionable()
        r['findings'][0]['figures'] = [figure()]
        r['findings'][0]['remediation']['steps'][0]['kind'] = 'COMPONENT'
        out = validate_review(p, r, db, require_actionable=True)
        self.assertFalse(out['valid'])
        r['findings'][0]['figures'].append(figure('AFTER', 'figures/F1-after.png'))
        out = validate_review(p, r, db, require_actionable=True)
        self.assertTrue(out['valid'], out['errors'])

    def test_a_p2_defect_may_go_without_figures(self):
        p, r, db = actionable()
        r['findings'][0].pop('figures', None)
        r['findings'][0]['severity'] = r['checks'][0]['severity'] = 'P2'
        out = validate_review(p, r, db, require_actionable=True)
        self.assertTrue(out['valid'], out['errors'])


class DesignOptionFigureTests(unittest.TestCase):
    def test_a_proposed_change_shows_the_circuit_before_and_after(self):
        p, r, db = gap_with_task(proposed_option(figures=[figure()]))
        out = validate_review(p, r, db, require_actionable=True)
        self.assertFalse(out['valid'])
        self.assertTrue(any('design_option' in e and 'AFTER' in e for e in out['errors']), out['errors'])
        p, r, db = gap_with_task(proposed_option(figures=[figure(), figure('AFTER', 'figures/W-after.png')]))
        out = validate_review(p, r, db, require_actionable=True)
        self.assertTrue(out['valid'], out['errors'])


class ReportTests(unittest.TestCase):
    def test_a_defect_reads_problem_consequence_figures_then_fix(self):
        p, r, db = actionable()
        f = r['findings'][0]
        f.update(root_cause='单级 TVS 的钳位电压高于 U1 引脚耐受，中间没有限流',
                 consequence='放电时 U1 引脚过压损坏，端口失效', fix='改成两级防护',
                 figures=[figure(), figure('REFERENCE', 'figures/F1-ref.png', '原厂典型应用：两级 TVS 加串阻')])
        text = render(p, r, validate_review(p, r, db, require_actionable=True))
        section = text.split('## 发现的错误')[1]
        self.assertIn('![每条线只有一颗 TVS，直接接到 U1](record/evidence/figures/F1-actual.png)', section)
        self.assertIn('图：现状。每条线只有一颗 TVS，直接接到 U1', section)
        self.assertIn('图：原厂参考。原厂典型应用：两级 TVS 加串阻', section)
        order = [section.index(x) for x in ('- **问题**：单级 TVS', '- **后果**：放电时', 'F1-actual.png',
                                            '- **怎么改**：改成两级')]
        self.assertEqual(order, sorted(order))
        html = to_html(text)   # the pictures of one card stand side by side, each captioned
        self.assertIn('<div class="figs">', html)
        self.assertIn('<figcaption>现状。每条线只有一颗 TVS，直接接到 U1</figcaption>', html)
        self.assertIn('<section class="card">', html)

    def test_a_caption_with_brackets_still_renders_as_an_image(self):
        p, r, db = actionable()
        r['findings'][0]['figures'] = [figure(caption='TVS (D702) 接到 U1 [p8]')]
        text = render(p, r, validate_review(p, r, db, require_actionable=True))
        self.assertIn('![TVS D702 接到 U1 p8](record/evidence/figures/F1-actual.png)', text)
        self.assertIn('图：现状。TVS (D702) 接到 U1 [p8]', text)
        self.assertIn('<img src="record/evidence/figures/F1-actual.png"', to_html(text))

    def test_a_proposed_change_shows_its_figures_under_the_work_item(self):
        p, r, db = gap_with_task(proposed_option(figures=[figure(), figure('AFTER', 'figures/W-after.png', '改后：从稳压轨经肖特基供电')]))
        text = render(p, r, validate_review(p, r, db, require_actionable=True))
        section = text.split('## 待办')[1]
        self.assertIn('](record/evidence/figures/W-after.png)', section)
        self.assertIn('图：改后：从稳压轨经肖特基供电', section)   # the caption names its kind: not prefixed again (5.1)


class RootCauseWordingTests(unittest.TestCase):
    def test_a_root_cause_that_only_names_the_missing_part_is_flagged(self):
        p, r, db = fixture(); fail(r)
        for cause in ('缺串阻和芯片端 TVS', '未加上拉电阻', '没有限流电阻'):
            with self.subTest(cause=cause):
                f = dict(r['findings'][0], root_cause=cause)
                self.assertEqual(['ROOT_CAUSE_IS_REMEDY'], [c['code'] for c in finding_wording([f])])
        f = dict(r['findings'][0], root_cause='加串阻', fix='加串阻')
        self.assertEqual(['ROOT_CAUSE_IS_REMEDY'], [c['code'] for c in finding_wording([f])])
        f = dict(r['findings'][0], root_cause='单级 TVS 的钳位电压高于引脚耐受，中间没有限流')
        self.assertEqual([], finding_wording([f]))
        for cause in ('缺口在 VCC 启动段：电压低于 VCC(off)', '缺省配置下 GPIO3 为高，PFC 一直禁能'):
            with self.subTest(cause=cause):
                self.assertEqual([], finding_wording([dict(r['findings'][0], root_cause=cause)]))


if __name__ == '__main__':
    unittest.main()
