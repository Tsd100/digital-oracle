import pytest

from digital_oracle.timeline.contract import ContractError, extract_trend_block


def report_with(payload: str) -> str:
    return f"# 黄金分析\n\n```do-trend\n{payload}\n```\n"


VALID = r'''{"schema_version":"1.0","analysis_id":"gold-1","analysis_at":"2026-09-21T14:30:00+08:00","data_as_of":"2026-09-21T14:00:00+08:00","subjects":[{"subject_id":"gold","subject_name":"黄金","instrument":"XAUUSD","quote_currency":"USD","quote_unit":"oz","horizons":{"short":{"direction":"bearish","confidence":72,"summary":"短线承压"},"medium":{"direction":"strong_bullish","confidence":78,"summary":"中期偏多"}}}]}'''


def test_extracts_versioned_trend_block():
    data = extract_trend_block(report_with(VALID))
    subject = data.subjects[0]
    assert data.schema_version == "1.0"
    assert subject.subject_id == "gold"
    assert subject.horizons["short"].direction == "bearish"
    assert "swing" not in subject.horizons


@pytest.mark.parametrize(
    "changed, message",
    [
        (VALID.replace('"bearish"', '"sideways"'), "direction"),
        (VALID.replace('"confidence":72', '"confidence":101'), "confidence"),
        (VALID.replace('"schema_version":"1.0"', '"schema_version":"2.0"'), "schema_version"),
    ],
)
def test_rejects_invalid_contract_values(changed, message):
    with pytest.raises(ContractError, match=message):
        extract_trend_block(report_with(changed))


def test_rejects_missing_or_multiple_blocks():
    with pytest.raises(ContractError, match="do-trend"):
        extract_trend_block("# no block")
    with pytest.raises(ContractError, match="exactly one"):
        extract_trend_block(report_with(VALID) + report_with(VALID))
