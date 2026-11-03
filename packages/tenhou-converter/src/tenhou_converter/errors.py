class ConversionError(ValueError):
    def __init__(
        self,
        reason: str,
        message: str,
        *,
        event_index: int | None = None,
        field: str | None = None,
    ) -> None:
        self.reason = reason
        self.message = message
        self.event_index = event_index
        self.field = field
        super().__init__(
            f"{reason}: {message} (event={event_index}, field={field})"
        )


class UnsupportedLogError(ConversionError):
    pass
