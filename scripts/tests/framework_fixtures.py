"""受控内容的测试用小框架：把真实框架里准则登记、词表和 G10 的数据文件复制到临时目录，测试改它的副本，
再用环境变量 HARDWARE_KNOWLEDGE_FRAMEWORK 指过去；七个知识组件和索引不复制（需要时测试自己写）。"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import knowledge_source as ks


def small_framework(dest):
    """在 dest 下建小框架并返回它的路径。"""
    real = ks.framework_root()
    dest = Path(dest)
    (dest / '知识').mkdir(parents=True, exist_ok=True)
    (dest / '索引').mkdir(exist_ok=True)
    files = sorted(ks.registry_dir().glob('G0*_准则登记.json')) + [
        ks.vocabulary_path(), ks.derating_path(), ks.commodity_path(), ks.derating_doc_path(), ks.stress_spec_path()]
    for path in files:
        target = dest / path.relative_to(real)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    return dest


def real_library():
    """框架里准则登记汇编出的完整准则库（含全部准则），不受 conftest 的“无规则”替换影响。"""
    import guideline_criteria as g
    return g.build(ks.registry_dir(), None, ks.vocabulary_path())
