from collections.abc import Sequence

import httpx

from app.core.config import settings


class RerankingService:
    def __init__(
        self,
        client: httpx.Client | None = None,
        model: str | None = None,
    ) -> None:
        self.client = client or httpx.Client(
            base_url=settings.siliconflow_base_url.rstrip("/"),
            headers={
                "Authorization": (
                    "Bearer "
                    + settings.secret_value(settings.siliconflow_api_key)
                )
            },
            timeout=30.0,
        )
        self.model = model or settings.reranker_model

    def rank(self, query: str, documents: Sequence[str]) -> list[int]:
        if not documents:
            return []

        response = self.client.post(
            "/rerank",
            json={
                "model": self.model,
                "query": query,
                "documents": list(documents),
                "top_n": len(documents),
                "return_documents": False,
            },
        )
        response.raise_for_status()
        payload = response.json()
        order = [int(item["index"]) for item in payload["results"]]
        if sorted(order) != list(range(len(documents))):
            raise ValueError("reranker returned invalid document indices")
        return order
