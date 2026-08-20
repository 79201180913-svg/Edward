from decimal import Decimal

from edward.history.trading_history import TradeRecord, TradingHistoryRepository


def test_history_read_and_idempotency(tmp_path):
    repo = TradingHistoryRepository(tmp_path / 'history.xlsx')
    record = TradeRecord(account_id='a', order_id='o', instrument_uid='u', operation='BUY', quantity=1, order_type='LIMIT', execution_price=Decimal('10'), amount=Decimal('10'), commission=Decimal('0.05'), currency='RUB', status='FILLED')
    repo.save_completed(record)
    repo.save_completed(record)
    rows = repo.read_all()
    assert len(rows) == 1
    assert rows[0]['order_id'] == 'o'
