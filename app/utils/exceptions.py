from fastapi import HTTPException, status

class ServiceNowConnectionError(Exception):
    """Raised when connection to ServiceNow fails (DNS, timeout, network)."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

def raise_gateway_error(msg: str):
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail={"error": "ServiceNowConnection", "message": msg}
    )
