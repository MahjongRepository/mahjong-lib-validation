import pytest
from tenhou_converter.errors import ConversionError
from tenhou_converter.parser import parse_xml


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
