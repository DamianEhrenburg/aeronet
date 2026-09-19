import time
import pytest
from aeronet_core.handlers import BotHandlers
from aeronet_core.database import Database
from aeronet_core.sheets import SheetsClient


@pytest.fixture
def handlers(tmp_path):
    db_path = str(tmp_path / "test.db")
    db = Database(db_path=db_path)
    db.init_db()
    sheets = SheetsClient()
    return BotHandlers(db=db, sheets=sheets)


def test_is_spam_debounce(handlers):
    user_id = 999
    # First click should not be throttled
    assert handlers._is_spam(user_id, cooldown=0.3) is False

    # Rapid second click (< 0.3s) must be throttled
    assert handlers._is_spam(user_id, cooldown=0.3) is True

    # After waiting longer than cooldown, should not be throttled
    time.sleep(0.35)
    assert handlers._is_spam(user_id, cooldown=0.3) is False
