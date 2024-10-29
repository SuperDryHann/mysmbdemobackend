import logging
import traceback
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist

# Configure your logger
logger = logging.getLogger(__name__)

class ErrorHandlingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)
        except PermissionDenied as ex:
            # Handle PermissionDenied with a 403 Forbidden status code
            logger.error("Permission Denied: %s", str(ex))
            return JsonResponse(
                {"error": "Permission denied", "details": str(ex)},
                status=403
            )
        except ObjectDoesNotExist as ex:
            # Handle ObjectDoesNotExist with a 404 Not Found status code
            logger.error("Object Not Found: %s", str(ex))
            return JsonResponse(
                {"error": "Object not found", "details": str(ex)},
                status=404
            )
        except Exception as ex:
            # Handle all other exceptions with a 500 Internal Server Error status code
            error_details = {
                "error_message": str(ex),
                "view_name": request.resolver_match.view_name if request.resolver_match else None,
                "traceback": traceback.format_exc(),
            }
            logger.error("Unhandled Exception: %s", error_details)

            return JsonResponse(
                {
                    "error": "A server error occurred.",
                    "details": error_details["error_message"],
                },
                status=500
            )

        return response
