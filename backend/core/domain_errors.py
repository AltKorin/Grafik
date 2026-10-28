"""Domain failure shared by input validation and HTTP services."""


class DomainError(Exception):
    def __init__(self, message, status=400):
        self.status = status
        super().__init__(message)
