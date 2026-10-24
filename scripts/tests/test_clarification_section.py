"""Requirement clarifications have their own section in the report (SR self-check 2.5, user: 单列一节).

An open clarification was shown only as a count under 定稿还差 and as a work item that left out what the requirement
says, the clause to add, who decides and by when. The report now lists each open clarification in
“需求要说清楚的地方”, and its work item points there instead of repeating it.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from render_report import render
from test_requirement_clarifications import covered, sample
from validate_review import validate_review

SECTION = '## 需求要说清楚的地方'


def report(p, r, db):
    gate = json.loads(json.dumps(validate_review(p, r, db), default=sorted))
    assert gate['valid'], gate['errors']
    return render(p, r, gate)


def section(text):
    return text.split(SECTION, 1)[1].split('\n## ', 1)[0]


class ClarificationSectionTests(unittest.TestCase):
    def test_an_open_clarification_says_what_the_requirement_says_and_what_to_add(self):
        p, r, db = sample()
        text = report(p, r, db)
        self.assertIn(SECTION, text)
        body = section(text)
        row = r['requirement_clarifications'][0]
        for field in ('title', 'requirement_text', 'question', 'decision_needed', 'proposed_requirement', 'owner',
                      'impact_reason', 'closure_criteria'):
            self.assertIn(row[field], body, field)
        self.assertIn('设计前', body)                      # decision_due BEFORE_DESIGN
        self.assertIn('不定下来不能定稿', body)             # freeze_impact BLOCKING
        self.assertIn('REQ-LOAD', body)
        self.assertIn('2 条检查', body)

    def test_the_work_item_points_at_the_section(self):
        p, r, db = sample()
        text = report(p, r, db)
        todo = text.split('## 待办', 1)[1].split('\n## ', 1)[0]
        self.assertIn('### CL-LOAD', todo)
        self.assertIn('需求要说清楚的地方', todo)
        self.assertNotIn(r['requirement_clarifications'][0]['impact_reason'], todo)

    def test_the_section_comes_before_the_work_items(self):
        p, r, db = sample()
        text = report(p, r, db)
        self.assertLess(text.index(SECTION), text.index('## 待办'))

    def test_a_covered_clarification_says_it_does_not_block(self):
        p, r, db = sample()
        covered(p, r)
        body = section(report(p, r, db))
        self.assertIn('不影响定稿', body)
        self.assertIn('后续确认', body)

    def test_no_open_clarification_no_section(self):
        p, r, db = sample()
        r['requirement_clarifications'][0]['status'] = 'RETRACTED'
        gate = json.loads(json.dumps(validate_review(p, r, db), default=sorted))
        self.assertNotIn(SECTION, render(p, r, gate))


if __name__ == '__main__':
    unittest.main()
