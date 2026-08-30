from app.schemas.dashboard import DashboardOverviewResponse
from app.services.dashboard import DashboardService


class FakeSession:
    def __init__(self, values: list[int | None]) -> None:
        self.values = iter(values)
        self.statements = []

    def scalar(self, statement):
        self.statements.append(statement)
        return next(self.values)


def test_get_dashboard_overview() -> None:
    session = FakeSession([3, 12, 8])

    result = DashboardService.get_overview(session)

    assert result == DashboardOverviewResponse(
        knowledge_base_count=3,
        processed_document_count=12,
        conversation_count=8,
    )
    assert len(session.statements) == 3


def test_get_dashboard_overview_normalizes_null_counts() -> None:
    session = FakeSession([None, None, None])

    result = DashboardService.get_overview(session)

    assert result.knowledge_base_count == 0
    assert result.processed_document_count == 0
    assert result.conversation_count == 0
