import json
import re

import httpx
from neo4j import GraphDatabase

from .common import digest


def entity_id(label):
    return digest(re.sub(r"\s+", " ", label.casefold()).strip().encode())[:24]


class Storage:
    def __init__(self, settings):
        self.http = httpx.Client(base_url=settings["opensearch_url"], timeout=120)
        self.graph = GraphDatabase.driver(settings["neo4j_url"], auth=None)

    def close(self):
        self.http.close()
        self.graph.close()

    def index_is_complete(self, manifest):
        name=manifest['index_name']
        response=self.http.get('/'+name+'/_count')
        if response.status_code==404:
            return False
        response.raise_for_status()
        if response.json()['count']!=manifest['chunks']+manifest['sections']:
            return False
        with self.graph.session() as session:
            graph_name=manifest.get('graph_name',name)
            chunks=session.run('MATCH (c:Chunk {version:$version}) RETURN count(c) AS n',version=graph_name).single()['n']
            facts=session.run('MATCH (f:Fact {version:$version}) RETURN count(f) AS n',version=graph_name).single()['n']
            orphans=session.run('MATCH (f:Fact {version:$version}) WHERE NOT (f)-[:EVIDENCED_BY]->(:Chunk) RETURN count(f) AS n',version=graph_name).single()['n']
        return chunks==manifest['chunks'] and facts==manifest['facts'] and orphans==0

    def create_index(self, name, dimensions):
        if self.http.head('/'+name).status_code == 200:
            return
        self.http.put('/'+name, json={"settings": {"number_of_shards": 1, "number_of_replicas": 0,
                                                    "index.knn": True},
            "mappings": {"properties": {"text": {"type": "text", "analyzer": "portuguese"},
                "metadata": {"type": "text", "analyzer": "portuguese"},
                "kind": {"type": "keyword"}, "corpus_id": {"type": "keyword"},
                "vector": {"type": "knn_vector", "dimension": dimensions},
                "chunk_ids": {"type": "keyword"}, "page": {"type": "integer"}}}}).raise_for_status()

    def put_records(self, name, records):
        lines = []
        for record in records:
            lines.extend([json.dumps({"index": {"_index": name, "_id": record["id"]}}), json.dumps(record)])
        if not lines:
            return
        response = self.http.post('/_bulk?refresh=true', content='\n'.join(lines)+'\n', headers={"Content-Type":"application/x-ndjson"})
        response.raise_for_status()
        data = response.json()
        if data["errors"]:
            raise RuntimeError(str([item for item in data["items"] if item["index"].get("error")])[:800])

    def search(self, index, query, vector=None, kind="chunk", limit=12):
        scope = {"term": {"kind": kind}}
        if vector is None:
            request = {"bool": {"filter": [scope], "must": [{"multi_match": {"query": query, "fields": ["text^2", "metadata"]}}]}}
        else:
            request = {"script_score": {"query": {"bool": {"filter": [scope]}},
                "script": {"source": "knn_score", "lang": "knn", "params": {"field": "vector", "query_value": vector, "space_type": "cosinesimil"}}}}
        response = self.http.post('/'+index+'/_search', json={"size": limit, "query": request,
                              "_source": {"excludes": ["vector"]}})
        response.raise_for_status()
        return [{**hit["_source"], "score": hit["_score"]} for hit in response.json()["hits"]["hits"]]

    def index_graph(self, version, chunks, facts):
        with self.graph.session() as session:
            session.run("CREATE CONSTRAINT chunk_key IF NOT EXISTS FOR (c:Chunk) REQUIRE c.key IS UNIQUE").consume()
            session.run("CREATE CONSTRAINT entity_key IF NOT EXISTS FOR (e:Entity) REQUIRE e.key IS UNIQUE").consume()
            session.run("CREATE CONSTRAINT fact_key IF NOT EXISTS FOR (f:Fact) REQUIRE f.key IS UNIQUE").consume()
            session.run("UNWIND $rows AS r MERGE (c:Chunk {key: r.key}) SET c.id=r.id, c.version=$version, c.page=r.page",
                        rows=[{"key": version+':'+c['id'], "id": c['id'], "page": c['page']} for c in chunks], version=version).consume()
            for fact in facts:
                session.run("""MERGE (s:Entity {key: $subject_key}) SET s.label=$subject, s.version=$version
                    MERGE (o:Entity {key: $object_key}) SET o.label=$object, o.version=$version
                    MERGE (f:Fact {key: $key}) SET f.predicate=$predicate, f.quote=$quote,
                        f.date=$date, f.speaker=$speaker, f.version=$version
                    MERGE (s)-[:SUBJECT_OF]->(f) MERGE (f)-[:OBJECT]->(o)
                    WITH f MATCH (c:Chunk {key: $chunk_key}) MERGE (f)-[:EVIDENCED_BY]->(c)""",
                    subject_key=version+':'+entity_id(fact['subject']), object_key=version+':'+entity_id(fact['object']),
                    key=version+':'+digest(json.dumps(fact,sort_keys=True).encode()), chunk_key=version+':'+fact['chunk_id'],
                    version=version, **{key: fact.get(key, '') for key in ['subject','object','predicate','quote','date','speaker']}).consume()

    def expand_graph(self, version, seeds, query, limit=12):
        with self.graph.session() as session:
            records = session.run("""MATCH (seed:Chunk {version:$version})<-[:EVIDENCED_BY]-(f:Fact)
                WHERE seed.id IN $seeds
                MATCH (e:Entity)-[:SUBJECT_OF|OBJECT]-(f)
                WITH DISTINCT e
                MATCH (e)-[:SUBJECT_OF|OBJECT]-(other:Fact)-[:EVIDENCED_BY]->(c:Chunk {version:$version})
                WHERE NOT c.id IN $seeds
                RETURN c.id AS id, count(DISTINCT other) AS weight ORDER BY weight DESC, id LIMIT $limit""",
                version=version, seeds=seeds, limit=limit)
            return [record['id'] for record in records]
