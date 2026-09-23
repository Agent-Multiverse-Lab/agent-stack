
"""Neo4j 知识图谱结构存储。"""

from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase, RoutingControl, basic_auth

from src.configs.config import config

_RELATION_TYPE = "RELATED_TO"

_store_instance: "Neo4jGraphStore | None" = None


class Neo4jGraphStore:
    """提供知识库实体与关系的 Neo4j 存取能力。"""

    def __init__(self) -> None:
        self._driver: AsyncDriver | None = None

    def _get_driver(self) -> AsyncDriver:
        """获取懒加载初始化的 Neo4j 异步驱动。"""
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                config.neo4j.uri,
                auth=basic_auth(config.neo4j.user, config.neo4j.password),
            )
        return self._driver

    async def upsert_entities(
        self,
        *,
        kb_id: str,
        file_id: str,
        entities: list[dict[str, Any]],
    ) -> None:
        """按 entity_id 写入或更新实体节点。"""
        if not entities:
            return
        await self._get_driver().execute_query(
            """
            UNWIND $entities AS e
            MERGE (n:Entity {entity_id: e.entity_id})
            SET n.kb_id = $kb_id,
                n.file_id = e.file_id,
                n.name = e.name,
                n.type = e.type,
                n.description = e.description
            """,
            kb_id=kb_id,
            entities=[{**entity, "file_id": file_id} for entity in entities],
        )

    async def create_relations(
        self,
        *,
        kb_id: str,
        file_id: str,
        relations: list[dict[str, Any]],
    ) -> None:
        """按两端实体 ID 写入命名关系。"""
        if not relations:
            return
        await self._get_driver().execute_query(
            f"""
            UNWIND $relations AS r
            MATCH (s:Entity {{entity_id: r.source_entity_id}})
            MATCH (t:Entity {{entity_id: r.target_entity_id}})
            MERGE (s)-[rel:{_RELATION_TYPE} {{kb_id: $kb_id, type: r.type}}]->(t)
            SET rel.relation_id = r.relation_id,
                rel.file_id = $file_id
            """,
            kb_id=kb_id,
            file_id=file_id,
            relations=relations,
        )

    async def get_graph(self, *, kb_id: str) -> dict[str, Any]:
        """读取知识库全量节点与边。"""
        driver = self._get_driver()
        node_result = await driver.execute_query(
            "MATCH (n:Entity {kb_id: $kb_id}) RETURN n",
            kb_id=kb_id,
            routing_=RoutingControl.READ,
        )
        edge_result = await driver.execute_query(
            f"""
            MATCH (s:Entity {{kb_id: $kb_id}})-[r:{_RELATION_TYPE} {{kb_id: $kb_id}}]->(t)
            RETURN r.relation_id AS relation_id,
                   r.type AS rel_type,
                   s.entity_id AS source_entity_id,
                   t.entity_id AS target_entity_id
            """,
            kb_id=kb_id,
            routing_=RoutingControl.READ,
        )
        nodes = [
            {
                "entity_id": record["n"]["entity_id"],
                "name": record["n"]["name"],
                "type": record["n"]["type"],
                "description": record["n"]["description"],
                "file_id": record["n"]["file_id"],
            }
            for record in node_result.records
        ]
        edges = [
            {
                "relation_id": record["relation_id"],
                "source_entity_id": record["source_entity_id"],
                "target_entity_id": record["target_entity_id"],
                "type": record["rel_type"],
            }
            for record in edge_result.records
        ]
        return {"nodes": nodes, "edges": edges}

    async def delete_by_file(self, *, kb_id: str, file_id: str) -> None:
        """删除指定文件抽取出的实体节点及其全部关系。"""
        await self._get_driver().execute_query(
            """
            MATCH (n:Entity {kb_id: $kb_id, file_id: $file_id})
            DETACH DELETE n
            """,
            kb_id=kb_id,
            file_id=file_id,
        )

    async def delete_by_kb(self, *, kb_id: str) -> None:
        """删除知识库全部实体节点及其全部关系。"""
        await self._get_driver().execute_query(
            "MATCH (n:Entity {kb_id: $kb_id}) DETACH DELETE n",
            kb_id=kb_id,
        )


def get_graph_store() -> Neo4jGraphStore:
    """获取单例图谱存储管理器。"""
    global _store_instance
    if _store_instance is None:
        _store_instance = Neo4jGraphStore()
    return _store_instance
