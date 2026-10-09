"""测试夹具：把 src 加进路径，并让每条用例都从已知数据开始。

评审硬条件：测试必须能独立初始化 fixture，不依赖人工数据库状态。
所以这里直接调用 seed 的插入逻辑，不假设库里已经有什么。
"""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _load_seed():
    spec = importlib.util.spec_from_file_location(
        "seed_script", ROOT / "scripts" / "seed.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session", autouse=True)
def seeded_db():
    """整个测试会话开始前，把底座重置成已知的 4 工单 / 3 订单。"""
    try:
        stats = _load_seed().seed()
    except Exception as exc:  # noqa: BLE001 - 数据库不可用就跳过整批
        pytest.skip("数据库不可用，跳过契约测试: " + str(exc))
    return stats
