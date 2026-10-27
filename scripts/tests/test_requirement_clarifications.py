"""Requirement questions are asked of the user at once and answered into the requirement list (2026-10-26).

User: 需求没定，那就需要及时和用户反馈，请用户澄清以后，马上修改需求清单，而不是放到最后; a 只允许采纳建议或明确暂缓;
b 无人值守时任务书附澄清答复，没覆盖的问题停在第①步. A question lives in intent.clarifications; a DECIDED or
ADOPTED_PROPOSAL answer is a requirement of its own, a DEFERRED answer defers the requirements it names, and a question
without an answer stops the review before the candidates. The results carry no undecided requirement and the report
lists the questions and their answers. A settled answer records whether the user let the original requirement files
be changed (user 2026-10-27: ASG和SR都需要提示用户，是否直接更改原始的需求文件。用户确认后，直接改). All evidence is
synthetic.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import circuit_candidates
import results_model
from plan_review import build_review_plan, validate_intent
from render_report import render
from test_requirement_source import requirement_intent
from test_validate_review import fixture
from validate_review import fingerprint, validate_review

PROPOSAL = '输出纹波不超过 50 mVpp（20 MHz 带宽，满载）'
ANSWERED = {'decision': 'ADOPTED_PROPOSAL', 'text': PROPOSAL, 'by': '需求负责人', 'date': '2026-10-26',
            'source': {'source': '对话记录', 'locator': '2026-10-26 需求澄清第 1 问'},
            'requirement_files': {'decision': 'UPDATED', 'files': ['/项目/需求规格.md']}}


def question(**changes):
    row = {'id': 'CL-RIPPLE', 'requirement_ids': ['REQ-OPEN-01'], 'question': '输出纹波限值没给，纹波检查没有判据',
           'requirement_text': 'REQ-OPEN-01：输出纹波限值待系统确定', 'proposed_requirement': PROPOSAL}
    row.update(changes)
    return row


def intent(row=None, ripple_status=None):
    out = dict({'schema_version': 5}, **requirement_intent())
    if row is not None:
        out['clarifications'] = [row]
    if row is not None and row.get('answer', {}).get('decision') in ('DECIDED', 'ADOPTED_PROPOSAL'):
        out['requirements'].append({'id': 'CL-RIPPLE', 'categories': ['OUTPUT_SPEC'], 'status': 'CONFIRMED',
                                    'interpretation': '主输出纹波按 50 mVpp 判'})
    if ripple_status:
        out['requirements'][2]['status'] = ripple_status
    return out


def empty_db():
    return {'parts': {}, 'nets': {}, 'pin2net': {}}


class AnswerTests(unittest.TestCase):
    def test_an_adopted_proposal_is_a_confirmed_requirement_of_its_own(self):
        value = intent(question(answer=ANSWERED))
        self.assertEqual(validate_intent(value), [])
        plan = build_review_plan(empty_db(), value)
        rows = [c for c in plan['checks'] if c['object'].get('requirement_id') == 'CL-RIPPLE']
        self.assertTrue(rows)
        self.assertEqual(rows[0]['source_text']['columns'], [{'name': 'text', 'text': PROPOSAL}])
        self.assertEqual(rows[0]['object']['requirement_status'], 'CONFIRMED')
        self.assertEqual([(c['id'], c['decision']) for c in plan['clarifications']], [('CL-RIPPLE', 'ADOPTED_PROPOSAL')])

    def test_the_answer_must_be_written_into_the_requirement_list(self):
        value = intent(question(answer=ANSWERED))
        value['requirements'].pop()
        self.assertTrue(any('intent.requirements 加一项 CL-RIPPLE' in e for e in validate_intent(value)))
        value = intent(question(answer=dict(ANSWERED, text='纹波随便')))
        self.assertTrue(any('一字不差' in e for e in validate_intent(value)))

    def test_a_user_decision_needs_who_when_and_where(self):
        answer = dict(ANSWERED, decision='DECIDED', text='输出纹波不超过 80 mVpp')
        del answer['source']
        errors = validate_intent(intent(question(answer=answer)))
        self.assertTrue(any('answer.source' in e for e in errors), errors)
        self.assertTrue(any('decision 须为' in e for e in validate_intent(intent(question(answer=dict(ANSWERED, decision='LATER'))))))

    def test_a_deferral_defers_the_requirements_it_names(self):
        deferral = dict(ANSWERED, decision='DEFERRED', text='纹波等系统方案定了再审')
        self.assertEqual(validate_intent(intent(question(answer=deferral), ripple_status='DEFERRED')), [])
        errors = validate_intent(intent(question(answer=deferral), ripple_status='CONFIRMED'))
        self.assertTrue(any('status 写 DEFERRED' in e for e in errors), errors)

    def test_an_undecided_or_proposed_status_is_refused(self):
        for status in ('OPEN', 'PROPOSED'):
            errors = validate_intent(intent(ripple_status=status))
            self.assertTrue(any('intent.clarifications' in e for e in errors), errors)


class RequirementFilesTests(unittest.TestCase):
    def test_a_settled_answer_without_the_file_question_is_refused(self):
        for decision, words in (('ADOPTED_PROPOSAL', PROPOSAL), ('DECIDED', '输出纹波不超过 80 mVpp')):
            answer = dict(ANSWERED, decision=decision, text=words)
            del answer['requirement_files']
            errors = validate_intent(intent(question(answer=answer)))
            self.assertTrue(any('requirement_files_not_asked' in e for e in errors), errors)
        answer = dict(ANSWERED, requirement_files={'decision': 'LATER'})
        errors = validate_intent(intent(question(answer=answer)))
        self.assertTrue(any('requirement_files_not_asked' in e for e in errors), errors)

    def test_updated_files_must_be_named(self):
        for files in (None, [], ['']):
            value = {'decision': 'UPDATED'} if files is None else {'decision': 'UPDATED', 'files': files}
            errors = validate_intent(intent(question(answer=dict(ANSWERED, requirement_files=value))))
            self.assertTrue(any('requirement_files_without_files' in e for e in errors), (files, errors))

    def test_files_the_user_kept_pass(self):
        for value in ({'decision': 'KEPT'}, {'decision': 'KEPT', 'files': []}):
            self.assertEqual(validate_intent(intent(question(answer=dict(ANSWERED, requirement_files=value)))), [])

    def test_a_deferral_is_not_asked_about_the_files(self):
        deferral = dict(ANSWERED, decision='DEFERRED', text='纹波等系统方案定了再审')
        del deferral['requirement_files']
        self.assertEqual(validate_intent(intent(question(answer=deferral), ripple_status='DEFERRED')), [])


class StopAtStepOneTests(unittest.TestCase):
    def test_an_unanswered_question_is_printed_by_the_cold_scan(self):
        value = intent(question(), ripple_status='DEFERRED')
        self.assertEqual(validate_intent(value), [])            # step ① keeps working while the user is asked
        plan = build_review_plan(empty_db(), value)
        self.assertEqual([d['code'] for d in plan['diagnostics'] if 'CL-RIPPLE' in d.get('detail', '')],
                         ['CLARIFICATION_PENDING'])

    def test_the_candidates_and_the_plan_with_candidates_refuse_it(self):
        value = intent(question(), ripple_status='DEFERRED')
        errors = validate_intent(value, candidates={'candidates': []})
        self.assertTrue(any('CL-RIPPLE 还没答复' in e for e in errors), errors)
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'db.json').write_text(json.dumps(empty_db()))
            (Path(tmp) / 'intent.json').write_text(json.dumps(value))
            with self.assertRaises(SystemExit) as stop:
                circuit_candidates.main([str(Path(tmp) / 'db.json'), '--intent', str(Path(tmp) / 'intent.json')])
        self.assertIn('CL-RIPPLE', str(stop.exception))


class ResultsAndReportTests(unittest.TestCase):
    def test_the_results_carry_no_clarification_list(self):
        found = results_model.shape_errors({'schema_version': results_model.SCHEMA_VERSION, 'functions': [],
                                            'checks': [], 'requirement_clarifications': []})
        self.assertTrue(any('intent.clarifications' in e for e in found), found)

    def test_the_report_lists_each_question_and_how_it_was_settled(self):
        p, r, db = fixture()
        p['clarifications'] = [{'id': 'CL-RIPPLE', 'requirement_ids': ['REQ-OPEN-01'],
                                'question': '输出纹波限值没给', 'requirement_text': 'REQ-OPEN-01：输出纹波限值待系统确定',
                                'decision': 'ADOPTED_PROPOSAL', 'text': PROPOSAL, 'by': '需求负责人', 'date': '2026-10-26',
                                'source': ANSWERED['source']}]
        r['plan_digest'] = fingerprint(p)
        gate = json.loads(json.dumps(validate_review(p, r, db), default=sorted))
        self.assertTrue(gate['valid'], gate['errors'])
        text = render(p, r, gate)
        body = text.split('## 需求澄清记录', 1)[1].split('\n## ', 1)[0]
        for words in ('CL-RIPPLE', '输出纹波限值没给', '采纳 SR 建议：' + PROPOSAL, '需求负责人', 'REQ-OPEN-01'):
            self.assertIn(words, body)


if __name__ == '__main__':
    unittest.main()
