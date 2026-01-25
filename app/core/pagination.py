from collections.abc import Sequence

from tortoise import Model
from tortoise.queryset import QuerySet


async def paginate_cursor[T: Model](
    queryset: QuerySet[T],
    cursor: int | None,
    limit: int,
    cursor_field: str = "id",
    order_by: str = "-id",
) -> tuple[Sequence[T], int | None]:
    """
    범용 커서 페이지네이션 함수
    """
    # 커서 필터 적용
    if cursor is not None:
        is_desc = order_by.startswith("-")
        op = "lt" if is_desc else "gt"  # less than(<), greater than(>)
        queryset = queryset.filter(**{f"{cursor_field}__{op}": cursor})

    # limit + 1개를 조회하여 다음 페이지 존재 여부 확인
    items = await queryset.order_by(order_by).limit(limit + 1)

    has_next = len(items) > limit
    items = items[:limit]

    next_cursor = getattr(items[-1], cursor_field) if has_next and items else None

    return items, next_cursor
