class BaseEmailProvider:
    def send(
        self,
        to_email: str,
        subject: str,
        html: str,
        text: str | None = None,
        *,
        from_email: str | None = None,
    ):
        raise NotImplementedError
