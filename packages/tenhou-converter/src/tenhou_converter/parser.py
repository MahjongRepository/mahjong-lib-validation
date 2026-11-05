from dataclasses import dataclass
from xml.etree import ElementTree as ET

from tenhou_converter.errors import ConversionError


class _TreeBuilder(ET.TreeBuilder):
    def doctype(
        self, _name: str, _pubid: str | None, _system: str | None
    ) -> None:
        msg = "invalid_xml"
        raise ConversionError(msg, "DOCTYPE and entities are unsupported")


@dataclass(frozen=True)
class Event:
    index: int
    tag: str
    attributes: dict[str, str]

    def text(self, field: str) -> str:
        try:
            return self.attributes[field]
        except KeyError as e:
            msg = "invalid_attribute"
            raise self.error(msg, "required attribute missing", field) from e

    def integer(self, field: str) -> int:
        values = self.numbers(field)
        if len(values) != 1:
            msg = "invalid_attribute"
            raise self.error(msg, "expected one integer", field)
        return values[0]

    def numbers(self, field: str) -> list[int]:
        value = self.text(field)
        try:
            return [int(part) for part in value.split(",")]
        except ValueError as e:
            msg = "invalid_attribute"
            raise self.error(msg, "expected integer list", field) from e

    def error(
        self, reason: str, message: str, field: str | None = None
    ) -> ConversionError:
        return ConversionError(
            reason, message, event_index=self.index, field=field
        )


def parse_xml(xml: bytes) -> list[Event]:
    try:
        root = ET.fromstring(  # noqa: S314 -- DTD rejected by target
            xml,
            parser=ET.XMLParser(target=_TreeBuilder()),  # noqa: S314 -- DTD rejected
        )
    except ConversionError:
        raise
    except (ET.ParseError, LookupError, ValueError) as e:
        msg = "invalid_xml"
        raise ConversionError(msg, str(e)) from e

    if root.tag != "mjloggm":
        msg = "invalid_xml"
        raise ConversionError(msg, "expected mjloggm root")
    if root.get("ver") != "2.3":
        msg = "unsupported_xml_version"
        raise ConversionError(msg, "expected version 2.3")
    if (root.text or "").strip() or any(
        len(element)
        or (element.text or "").strip()
        or (element.tail or "").strip()
        for element in root
    ):
        msg = "invalid_xml"
        raise ConversionError(msg, "expected flat, empty event elements")
    return [
        Event(i, element.tag, dict(element.attrib))
        for i, element in enumerate(root)
    ]
