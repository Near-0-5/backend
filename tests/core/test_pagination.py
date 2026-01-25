import pytest
from tortoise import fields
from tortoise.models import Model

from app.core.pagination import paginate_cursor


class TestItem(Model):
    __test__ = False

    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=50)

    class Meta:
        table = "test_items"
        app = "models"


@pytest.fixture
async def sample_items():
    await TestItem.all().delete()

    items = [
        await TestItem.create(name="a"),
        await TestItem.create(name="b"),
        await TestItem.create(name="c"),
        await TestItem.create(name="d"),
        await TestItem.create(name="e"),
    ]
    return items


@pytest.mark.asyncio
async def test_first_page_desc(sample_items):
    queryset = TestItem.all()

    items, next_cursor = await paginate_cursor(
        queryset=queryset,
        cursor=None,
        limit=2,
        order_by="-id",
    )

    assert [item.name for item in items] == ["e", "d"]
    assert next_cursor == items[-1].id


@pytest.mark.asyncio
async def test_second_page_desc(sample_items):
    queryset = TestItem.all()

    first_items, cursor = await paginate_cursor(
        queryset=queryset,
        cursor=None,
        limit=2,
        order_by="-id",
    )

    second_items, next_cursor = await paginate_cursor(
        queryset=queryset,
        cursor=cursor,
        limit=2,
        order_by="-id",
    )

    assert [item.name for item in second_items] == ["c", "b"]
    assert next_cursor == second_items[-1].id


@pytest.mark.asyncio
async def test_last_page_no_next_cursor(sample_items):
    queryset = TestItem.all()

    _, cursor = await paginate_cursor(queryset, None, limit=4, order_by="-id")
    items, next_cursor = await paginate_cursor(queryset, cursor, limit=4, order_by="-id")

    assert len(items) == 1
    assert next_cursor is None


@pytest.mark.asyncio
async def test_asc_order(sample_items):
    queryset = TestItem.all()

    items, next_cursor = await paginate_cursor(
        queryset=queryset,
        cursor=None,
        limit=3,
        order_by="id",
    )

    assert [item.name for item in items] == ["a", "b", "c"]
    assert next_cursor == items[-1].id
