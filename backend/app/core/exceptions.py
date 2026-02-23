class AppException(Exception):
    def __init__(self, message: str, code: str = "APP_ERROR", status_code: int = 500):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class AuthenticationError(AppException):
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, "AUTHENTICATION_ERROR", 401)


class AuthorizationError(AppException):
    def __init__(self, message: str = "Access denied"):
        super().__init__(message, "AUTHORIZATION_ERROR", 403)


class NotFoundError(AppException):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, "NOT_FOUND", 404)


class SessionNotFoundError(NotFoundError):
    def __init__(self):
        super().__init__("Session not found")


class UserNotFoundError(NotFoundError):
    def __init__(self):
        super().__init__("User not found")


class SessionLimitExceededError(AppException):
    def __init__(self, current: int, max_sessions: int):
        super().__init__(
            f"Maximum concurrent sessions limit reached ({current}/{max_sessions})",
            "SESSION_LIMIT_EXCEEDED",
            403,
        )
        self.current = current
        self.max_sessions = max_sessions


class DailyQuotaExceededError(AppException):
    def __init__(self):
        super().__init__("Daily session quota exceeded", "DAILY_QUOTA_EXCEEDED", 403)


class GottyStartupError(AppException):
    def __init__(self, message: str = "Failed to start Gotty"):
        super().__init__(message, "GOTTY_STARTUP_ERROR", 500)


class NoAvailablePortError(AppException):
    def __init__(self):
        super().__init__("No available ports", "NO_AVAILABLE_PORT", 503)


class IAMSyncError(AppException):
    def __init__(self, message: str = "IAM sync failed"):
        super().__init__(message, "IAM_SYNC_ERROR", 500)


class SAMLError(AppException):
    def __init__(self, message: str = "SAML error"):
        super().__init__(message, "SAML_ERROR", 400)
