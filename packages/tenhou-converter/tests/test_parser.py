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
