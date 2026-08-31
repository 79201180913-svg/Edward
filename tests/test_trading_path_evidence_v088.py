from edward.services.trading_path_evidence_v088 import TradingPathEvidenceServiceV088


def test_temporal_blocks_preserve_order_and_cover_all_returns():
    blocks = TradingPathEvidenceServiceV088.temporal_blocks((1.0, 2.0, -1.0, 4.0, 2.0, 3.0), blocks=3)
    assert blocks == (1.5, 1.5, 2.5)


def test_evidence_requires_all_temporal_blocks_to_be_positive_for_stability():
    evidence = TradingPathEvidenceServiceV088.build((1.0, 2.0, -5.0, 2.0, 2.0, 3.0))
    assert evidence.temporal_block_count == 3
    assert evidence.temporal_positive_blocks == 2
    assert evidence.temporal_stable is False


def test_evidence_clamps_overlap_and_testing_metadata():
    evidence = TradingPathEvidenceServiceV088.build((1.0, 2.0), overlap_max_ratio=2.0, multiple_testing_count=0, multiple_testing_rank=0)
    assert evidence.overlap_max_ratio == 1.0
    assert evidence.multiple_testing_count == 1
    assert evidence.multiple_testing_rank == 1
