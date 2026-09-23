"""知识图谱抽取器测试。"""

import unittest
from types import SimpleNamespace

from src.knowledge.graph.extractor import (
    GraphEntity,
    GraphExtractionResult,
    GraphExtractor,
    GraphRelation,
)


class FakeStructuredRunnable:
    """返回固定结构化结果。"""

    def __init__(self, result):
        self.result = result

    async def ainvoke(self, messages):
        """返回固定结果。"""
        return self.result


class FakeModel:
    """模拟结构化输出成功或失败的语言模型。"""

    def __init__(self, *, structured_result=None, structured_error=None, text=""):
        self.structured_result = structured_result
        self.structured_error = structured_error
        self.text = text

    def with_structured_output(self, schema):
        """模拟结构化输出装配，可注入失败。"""
        if self.structured_error is not None:
            raise self.structured_error
        return FakeStructuredRunnable(self.structured_result)

    async def ainvoke(self, messages):
        """返回 JSON 文本。"""
        return SimpleNamespace(text=self.text)


class GraphExtractorTest(unittest.IsolatedAsyncioTestCase):
    async def test_extract_uses_structured_output(self) -> None:
        """结构化输出可用时直接返回抽取结果。"""
        expected = GraphExtractionResult(
            entities=[GraphEntity(name="OpenAI", type="组织")],
            relations=[],
        )
        extractor = GraphExtractor(model=FakeModel(structured_result=expected))

        result = await extractor.extract("# Document")

        self.assertEqual("OpenAI", result.entities[0].name)

    async def test_extract_falls_back_to_json_text(self) -> None:
        """结构化输出失败时回退 JSON 文本解析。"""
        model = FakeModel(
            structured_error=NotImplementedError("unsupported"),
            text='```json\n{"entities": [{"name": "DeepSeek", "type": "组织"}],'
            ' "relations": [{"source": "DeepSeek", "target": "V4", "type": "发布"}]}\n```',
        )
        extractor = GraphExtractor(model=model)

        result = await extractor.extract("# Document")

        self.assertEqual("DeepSeek", result.entities[0].name)
        self.assertEqual(
            GraphRelation(source="DeepSeek", target="V4", type="发布"),
            result.relations[0],
        )

    async def test_extract_accepts_plain_list_json(self) -> None:
        """回退解析容忍纯列表形式的 JSON。"""
        model = FakeModel(
            structured_error=RuntimeError("boom"),
            text='[{"name": "Milvus", "type": "技术"}]',
        )
        extractor = GraphExtractor(model=model)

        result = await extractor.extract("# Document")

        self.assertEqual("Milvus", result.entities[0].name)
        self.assertEqual([], result.relations)


if __name__ == "__main__":
    unittest.main()
