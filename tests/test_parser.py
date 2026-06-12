from hermes_medical_agent.parser import parse_caption


def test_parse_caption_english_fields():
    result = parse_caption("type: EGD\ndate: 2026-06-10\ncomment: stomach pain")
    assert result.document_type == "EGD"
    assert result.document_date == "2026-06-10"
    assert result.comment == "stomach pain"


def test_parse_caption_russian_fields():
    result = parse_caption("тип: флюорография\nдата: 2026-06\nкомментарий: плановый осмотр")
    assert result.document_type == "флюорография"
    assert result.document_date == "2026-06"
    assert result.comment == "плановый осмотр"
