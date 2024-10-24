# This is customised authenticatio classes for WSGI (http) and ASGI (websocket).

# AzureJWTAuthenticate class is the main clss that is responsible to authenticate user via validating jwt with Azure Entra. The class is set as simple jwt's middle ware in settings.py. 
# - Its get_validated_token and get_user methods are overriden. The get_validated_token method now use AzureAccessToken class rather than AccessToken class.
# - The get_user method now uses get_or_create() rather than get() to create user if a user is not on user model. As jwt is always validated first with Azure Entra, this is safe.

# AzureAccessToken class overrides get_token_backend() and verify() method.
# - The get_token_backend() specifies now to use AzureTokenbackend class rather than TokenBakend class.
# - The verify() method inherits its previous method and it adds id, jti and token_type as Azure Entra jwt doesn't have the claims. This is safe as jwt is validated with Azure Entra in previous step.

# AzureTokenBackend class overrides decode() method. This is the most critical method as it validates jwt with Azure Entra. Only change is issuer it to use dynamic issuer which contains each tenant. 



from base.models import User
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken, TokenError
from django.conf import settings
from rest_framework_simplejwt.backends import TokenBackend
from jwt.exceptions import InvalidAlgorithmError, InvalidTokenError
from rest_framework_simplejwt.exceptions import TokenBackendError
from typing import Any, Dict
from rest_framework_simplejwt.tokens import Token
import jwt
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.utils import get_md5_hash_password
from django.contrib.auth.models import AbstractBaseUser
from rest_framework_simplejwt.models import TokenUser
from typing import TypeVar
from django.utils.translation import gettext_lazy as _



# Http authentication middleware
class AzureTokenBackend(TokenBackend):
    def __init__(
            self, 
            algorithm, 
            signing_key=None, 
            verifying_key=None, 
            audience=None, 
            issuer=None, 
            jwk_url=None
            ):
        super().__init__(
            algorithm, 
            signing_key, 
            verifying_key, 
            audience, 
            issuer,
            jwk_url
            )



    def decode(self, token: Token, verify: bool = True) -> Dict[str, Any]:
        """
        Override token decoding to handle Azure Entra JWT. Dynamic issuer is implemented depend on tenant id (tid claim).
        Only issure is modified. The rest of the validation is the same as the default TokenBackend.
        """
        try:
            # Decode the token without verification to extract 'tid'
            unverified_payload = jwt.decode(token, options={"verify_signature": False})
        except jwt.PyJWTError as e:
            raise TokenBackendError(f"Invalid token: {str(e)}")

        # Extract 'tid' (tenant ID) from the token
        tenant_id = unverified_payload.get('tid')
        if not tenant_id:
            raise TokenBackendError("Token does not contain 'tid' (tenant ID) claim.")

        # Construct the dynamic issuer using the 'tid'
        dynamic_issuer = f'https://sts.windows.net/{tenant_id}/'


        try:
            return jwt.decode(
                token,
                self.get_verifying_key(token),
                algorithms=[self.algorithm],
                audience=self.audience,
                issuer=dynamic_issuer,
                leeway=self.get_leeway(),
                options={
                    "verify_aud": self.audience is not None,
                    "verify_signature": verify,
                },
            )
        except InvalidAlgorithmError as ex:
            raise TokenBackendError(_("Invalid algorithm specified")) from ex
        except InvalidTokenError as ex:
            raise TokenBackendError(_("Token is invalid or expired")) from ex



class AzureAccessToken(AccessToken):
    '''
    Override get_token_backend to use AzureTokenBackend. Original method calls TokenBackend class
    '''
    def get_token_backend(self):
        return AzureTokenBackend(
            algorithm='RS256',
            signing_key=None,
            verifying_key=None,
            audience=f'api://{os.getenv("FRONTEND_DOMAIN")}/{os.getenv("AZURE_ENTRA_CLIENT_ID")}',
            jwk_url='https://login.microsoftonline.com/common/discovery/v2.0/keys',
            issuer=None,
        )



    # Add missing claims in Azure jwt
    def verify(self):
        '''
        This is invoked after .decode method which is responsible to validate and decode jwt. So, this addition is safe to implement.
        '''
        # Inject 'id' with 'sub' as Azure jwt is missing id field
        if 'id' not in self.payload:
            self.payload['id'] = self.payload.get('sub', None)
            if self.payload['id'] is None:
                raise TokenError("Token has neither 'id' nor 'sub' field.")

        # Inject 'id' with 'sub' as Azure jwt is missing id field
        if 'jti' not in self.payload:
            self.payload['jti'] = self.payload.get('sub', None)

        # Inject 'token_type' if missing
        if 'token_type' not in self.payload:
            self.payload['token_type'] = 'access'

        try:
            super().verify()
        except TokenError as e:
            raise TokenError(f"Token verification failed: {str(e)}")




class AzureJWTAuthentication(JWTAuthentication):
    def get_validated_token(self, raw_token: bytes) -> Token:
        """
        Override the class to use AzureAccessToken class rather than AccessToken (api_settings.AUTH_TOKEN_CLASSES)
        """
        messages = []
        try:
            return AzureAccessToken(raw_token) # This line is changed to use the class rather than AccessToken class. Could change setting to ensure use this class, but in this way, less configuration.  
        except TokenError as e:
            messages.append(
                {
                    "token_class": AzureAccessToken.__name__,
                    "token_type": AzureAccessToken.token_type,
                    "message": e.args[0],
                }
            )

        raise InvalidToken(
            {
                "detail": _("Given token not valid for any token type"),
                "messages": messages,
            }
        )



    AuthUser = TypeVar("AuthUser", AbstractBaseUser, TokenUser)

    def get_user(self, validated_token: Token) -> AuthUser:
        """
        Attempts to find and return a user using the given validated token.
        """
        try:
            user_id = validated_token["id"] # change to id from user_id. id is sub claim which is global unique
        except KeyError:
            raise InvalidToken(_("Token contained no recognizable user identification"))

        try:
            user, created = User.objects.get_or_create(username=user_id) # Change to get or create from get
        except:
            raise AuthenticationFailed(_("User not found"), code="user_not_found")

        if not user.is_active:
            raise AuthenticationFailed(_("User is inactive"), code="user_inactive")

        if api_settings.CHECK_REVOKE_TOKEN:
            if validated_token.get(
                api_settings.REVOKE_TOKEN_CLAIM
            ) != get_md5_hash_password(user.password):
                raise AuthenticationFailed(
                    _("The user's password has been changed."), code="password_changed"
                )
        return user



# AzureJWTAuthenticationWS middleware is called with any asgi request. The class start with extracting "access_token" from websocket url.
# - Extract "access_token" from websocket url
# - Pass the token to get_validated_token() method. The method is responsible to validate and decode the access token.
# - The get_user() method get or create user from validated token from step above by id claim

# The get_validated_token() method validate token with AzureAccessToken class. AzureAccessToken class overrides get_token_backend() and verify() method.
# - The get_token_backend() specifies now to use AzureTokenbackend class rather than TokenBakend class.
# - The verify() method inherits its previous method and it adds id, jti and token_type as Azure Entra jwt doesn't have the claims. This is safe as jwt is validated with Azure Entra in previous step.

# The websocket_authenticated decorator is defined to check "is_authenticated" is true in the user found from the above step. If it is not true, it stop the process. 


# Websocket authentication middleware
import os
import jwt
from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser



class AzureJWTAuthenticationWS(BaseMiddleware):

    async def __call__(self, scope, receive, send):
        # Extract access token
        query_string = scope.get("query_string", b"").decode()
        query_params = parse_qs(query_string)
        raw_token = query_params.get("access_token", [None])[0].encode()

        if raw_token is None:
            scope["user"] = AnonymousUser()
            return await self.inner(scope, receive, send)

        validated_token = self.get_validated_token(raw_token)

        user = await self.get_user(validated_token)

        scope["user"] = user

        return await self.inner(scope, receive, send)
    


    def get_validated_token(self, raw_token: bytes) -> Token:
        """
        Override the class to use AzureAccessToken class rather than AccessToken (api_settings.AUTH_TOKEN_CLASSES)
        """
        messages = []
        try:
            return AzureAccessToken(raw_token) # This line is changed to use the class rather than AccessToken class. Could change setting to ensure use this class, but in this way, less configuration.  
        except TokenError as e:
            messages.append(
                {
                    "token_class": AzureAccessToken.__name__,
                    "token_type": AzureAccessToken.token_type,
                    "message": e.args[0],
                }
            )

        raise InvalidToken(
            {
                "detail": _("Given token not valid for any token type"),
                "messages": messages,
            }
        )



    @database_sync_to_async
    def get_or_create_user(self, username):
        user, created = User.objects.get_or_create(username=username)
        return user
    


    AuthUser = TypeVar("AuthUser", AbstractBaseUser, TokenUser)

    async def get_user(self, validated_token: Token) -> AuthUser:
        """
        Attempts to find and return a user using the given validated token.
        """
        try:
            user_id = validated_token["id"] # change to id from user_id. id is sub claim which is global unique

        except KeyError:
            raise InvalidToken(_("Token contained no recognizable user identification"))

        try:
            user = await self.get_or_create_user(username = user_id) # Change to get or create from get

        except:
            raise AuthenticationFailed("User not found", code="user_not_found")

        if not user.is_active:
            raise AuthenticationFailed("User is inactive", code="user_inactive")

        if api_settings.CHECK_REVOKE_TOKEN:
            if validated_token.get(
                api_settings.REVOKE_TOKEN_CLAIM
            ) != get_md5_hash_password(user.password):
                raise AuthenticationFailed(
                    _("The user's password has been changed."), code="password_changed"
                )
        return user



# Decorator to check if user is authenticated
from functools import wraps
from channels.exceptions import DenyConnection
from channels.db import database_sync_to_async

# Decorator to check if user is authenticated
def websocket_authenticated(func):
    @wraps(func)
    async def inner(self, *args, **kwargs):
        # Check if the user is authenticated
        if not self.scope["user"].is_authenticated:
            await self.close(code=4001)  # Custom close code for unauthenticated users
            return  # Prevent further execution if not authenticated
        return await func(self, *args, **kwargs)
    return inner