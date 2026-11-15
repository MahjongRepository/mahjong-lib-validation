import pytest
from tenhou_converter.errors import ConversionError
from tenhou_converter.parser import Event, parse_xml


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16", "utf-32"])
def test_doctype_is_rejected_before_expanding_entities(encoding: str) -> None:
    xml = (
        '<?xml version="1.0" encoding="'
        + encoding
        + '"?><!DOCTYPE mjloggm [<!ENTITY x "2.3">]><mjloggm ver="&x;"/>'
    )
    with pytest.raises(ConversionError, match="invalid_xml"):
        parse_xml(xml.encode(encoding))


@pytest.mark.parametrize("encoding", ["nonexistent-encoding", "utf-7"])
def test_invalid_encoding_declaration_is_a_conversion_error(
    encoding: str,
) -> None:
    xml = (
        f'<?xml version="1.0" encoding="{encoding}"?><mjloggm ver="2.3"/>'
    ).encode("ascii")

    with pytest.raises(ConversionError) as caught:
        parse_xml(xml)

    assert caught.value.reason == "invalid_xml"
    assert caught.value.__cause__ is not None


@pytest.mark.parametrize(
    "body",
    [
        "text<GO/>",
        "<GO><UN/></GO>",
        "<GO>text</GO>",
        "<GO/>text<UN/>",
        "<GO/>text",
    ],
    ids=[
        "root-text",
        "nested-event",
        "event-text",
        "between-events",
        "trailing-text",
    ],
)
def test_invalid_document_structure_preserves_error_details(body: str) -> None:
    xml = f'<mjloggm ver="2.3">{body}</mjloggm>'.encode()

    with pytest.raises(ConversionError) as caught:
        parse_xml(xml)

    assert caught.value.reason == "invalid_xml"
    assert caught.value.field is None
    assert caught.value.event_index is None


@pytest.mark.parametrize(
    "body",
    ['<GO type="41"/><UN/>', ' \n<GO type="41"> \t </GO>\n<UN/>\r\n'],
    ids=["compact", "whitespace"],
)
def test_flat_document_accepts_whitespace_and_preserves_events(
    body: str,
) -> None:
    xml = f'<mjloggm ver="2.3">{body}</mjloggm>'.encode()

    events = parse_xml(xml)

    assert events == [Event(0, "GO", {"type": "41"}), Event(1, "UN", {})]
