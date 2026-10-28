"""Errors safe to expose at the API boundary."""


class EngineError(Exception):
    code = "engine_error"
    status_code = 500


class InvalidDocument(EngineError):
    code = "invalid_document"
    status_code = 422


class NotFound(EngineError):
    code = "not_found"
    status_code = 404


class ProviderError(EngineError):
    code = "provider_unavailable"
    status_code = 503


class BusyError(EngineError):
    code = "busy"
    status_code = 429


class ConflictError(EngineError):
    code = "document_conflict"
    status_code = 409
