"""SR reviews from the requirements and the design results, not from the designer's documents.

SR reads the requirements, the design results (schematic, netlist, BOM, schematic PDF), manufacturer and standards
documents and its own calculations. The designer's own documents (design report, design proposal, calculation file,
electrical intent, requirement trace, device contracts, self-check and delivery records, replies to earlier comments)
state what the designer meant or believes; taking them as a citation or as row evidence lets them set the review.
A citation in the review intent or a row evidence that names one is refused. Facts the schematic cannot show go to the
designer as a handoff and come back as a requirement or an input.
"""
import re

# Words a designer document is named by, matched in a citation or an evidence path (case-insensitive); a folder
# named 设计方案/ holds the design results too, so only a file or a text naming the design proposal counts.
DESIGNER_DOCUMENT_RE = re.compile(
    r'设计报告|设计说明|设计方案(?!/)|计算书|design[ _-]?report|design[ _-]?proposal|electrical[_-]intent|'
    r'requirement[_-]trace|device[_-]contracts|delivery[_-]evidence|(?<!calculation-)preflight|review[_-]responses|'
    r'lessons\.json|selection\.json|visual[_-]review|downstream[_-]constraints|record/calculations/', re.I)


def designer_document(text):
    """The designer-document word `text` names, or None."""
    match = DESIGNER_DOCUMENT_RE.search(text) if isinstance(text, str) else None
    return match.group(0) if match else None


def intent_errors(intent, path='intent'):
    """Every string in the review intent that cites a designer document."""
    errors = []
    if isinstance(intent, dict):
        for key, value in intent.items():
            errors.extend(intent_errors(value, '%s.%s' % (path, key)))
    elif isinstance(intent, list):
        for index, value in enumerate(intent):
            errors.extend(intent_errors(value, '%s[%d]' % (path, index)))
    elif designer_document(intent):
        errors.append('%s 引用了设计方文档（%s）：SR 只从需求、设计结果（原理图、网表、BOM、PDF）和原厂资料独立判断；'
                      '原理图上看不出的事实写成移交项，请设计方确认后作为需求或输入' % (path[len('intent.'):], designer_document(intent)))
    return errors


def evidence_errors(checks):
    """Every row evidence whose source is a designer document."""
    errors = []
    for check in checks:
        for item in check.get('evidence') or [] if isinstance(check, dict) else []:
            source = item.get('source') if isinstance(item, dict) else None
            if designer_document(source):
                errors.append('%s: 证据来自设计方文档 %s（%s）；按需求、设计结果和原厂资料自己算，不引用设计方的结论'
                              % (check.get('id'), source, designer_document(source)))
    return errors
