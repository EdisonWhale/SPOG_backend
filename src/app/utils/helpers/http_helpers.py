import httpx

class HttpHelpers:
    
    @staticmethod
    def is_500_error(http_error: httpx.HTTPStatusError):
        """
        Checks whether or not the exception is an httpx.HTTPStatusError with a 500 status code.
        """
        return isinstance(http_error, httpx.HTTPStatusError) and http_error.response.status_code >= 500
