"""Domain failure shared by input validation and HTTP services.

The message is a Polish template ("Pole „{label}” jest wymagane") plus params, so the HTTP layer can answer
in English (core.i18n.tr) while str(error) stays the Polish sentence for logs and tests."""


class DomainError(Exception):
    def __init__(self, message, status=400, **params):
        self.status, self.template, self.params = status, message, params
        super().__init__(message.format(**params) if params else message)
