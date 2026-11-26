"""Decode caller-supplied replay data using the liqi protobuf schema."""

from google.protobuf.message import DecodeError, Message
from google.protobuf.message_factory import GetMessageClass

from majsoul_converter.liqi import liqi_pb2 as pb

_RANKED_CATEGORY = 2
_RESPONSE_KIND = 3
_RESPONSE_HEADER_SIZE = 3


class ConversionError(ValueError):
    pass


def _unwrap(payload: bytes) -> Message:
    wrapper = pb.Wrapper.FromString(payload)
    name = wrapper.name.removeprefix(".")
    try:
        descriptor = pb.DESCRIPTOR.pool.FindMessageTypeByName(name)
    except KeyError as e:
        msg = f"unknown replay message {wrapper.name!r}"
        raise ConversionError(msg) from e
    return GetMessageClass(descriptor).FromString(wrapper.data)


def _response(payload: bytes) -> tuple[str | None, bytes]:
    if payload[:1] == bytes([_RESPONSE_KIND]):
        wrapper = pb.Wrapper.FromString(payload[_RESPONSE_HEADER_SIZE:])
        if wrapper.name:
            msg = "Response Wrapper must have an empty name"
            raise ConversionError(msg)
        payload = wrapper.data

    response = pb.ResGameRecord.FromString(payload)
    if response.error.code:
        msg = f"fetchGameRecord returned error {response.error.code}"
        raise ConversionError(msg)
    if (
        response.head.HasField("config")
        and response.head.config.category != _RANKED_CATEGORY
    ):
        msg = "only ranked replays are supported"
        raise ConversionError(msg)
    if not response.data:
        msg = "response has no embedded replay; supply the replay data"
        raise ConversionError(msg)
    return response.head.uuid or None, response.data


def decode(payload: bytes) -> tuple[str | None, list[tuple[int, Message]]]:
    log_id = None
    try:
        if (
            payload[:1] == bytes([_RESPONSE_KIND])
            or not pb.Wrapper.FromString(payload).name
        ):
            log_id, payload = _response(payload)
        detail = _unwrap(payload)
        if not isinstance(detail, pb.GameDetailRecords):
            msg = "expected a GameDetailRecords Wrapper"
            raise ConversionError(msg)
        records = (
            (
                (index, action.result)
                for index, action in enumerate(detail.actions)
                if action.result
            )
            if detail.actions
            else enumerate(detail.records)
        )
        events = [(index, _unwrap(record)) for index, record in records]
    except DecodeError as e:
        msg = f"invalid replay protobuf: {e}"
        raise ConversionError(msg) from e
    return log_id, events
