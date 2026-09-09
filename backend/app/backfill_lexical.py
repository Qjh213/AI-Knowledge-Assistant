"""Backfill the sidecar Milvus BM25 collection from dense chunk records."""

from app.services.vector_store import VectorStoreService


def main() -> None:
    store = VectorStoreService()
    store.ensure_collection()
    store.ensure_lexical_collection()
    fields = [
        "id", "knowledge_base_id", "document_id", "chunk_index",
        "content", "page_number", "token_count", "metadata",
    ]
    iterator = store.client.query_iterator(
        collection_name=store.collection_name,
        batch_size=500,
        output_fields=fields,
    )
    total = 0
    try:
        while True:
            batch = iterator.next()
            if not batch:
                break
            store.client.upsert(
                collection_name=store.lexical_collection_name,
                data=batch,
            )
            total += len(batch)
            print(f"Backfilled {total} chunks")
    finally:
        iterator.close()

    store.client.flush(store.lexical_collection_name)
    store.client.load_collection(store.lexical_collection_name)
    dense_count = total
    visible = store.client.query_iterator(
        collection_name=store.lexical_collection_name,
        batch_size=1000,
        output_fields=["id"],
    )
    lexical_ids: set[str] = set()
    try:
        while True:
            batch = visible.next()
            if not batch:
                break
            lexical_ids.update(str(row["id"]) for row in batch)
    finally:
        visible.close()
    lexical_count = len(lexical_ids)
    if lexical_count != dense_count:
        raise RuntimeError(
            f"lexical backfill incomplete: dense={dense_count}, lexical={lexical_count}"
        )
    print(f"Lexical index ready: dense={dense_count}, lexical={lexical_count}")


if __name__ == "__main__":
    main()
