from base.models import User
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken, TokenError
from django.conf import settings
from rest_framework_simplejwt.backends import TokenBackend
import jwt



# Http authentication middleware
class AzureTokenBackend(TokenBackend):
    def __init__(self, algorithm, signing_key=None, verifying_key=None, audience=None, issuer=None, jwk_url=None):
        super().__init__(algorithm, signing_key, verifying_key, audience, issuer)
        self.jwk_url = jwk_url


    def decode(self, token, verify=True):
        # Decode the token without verification to extract 'tid'
        try:
            unverified_payload = jwt.decode(token, options={"verify_signature": False})
        except jwt.PyJWTError as e:
            raise TokenError(f"Invalid token: {str(e)}")

        # Extract 'tid' (tenant ID) from the token
        tenant_id = unverified_payload.get('tid')
        if not tenant_id:
            raise TokenError("Token does not contain 'tid' (tenant ID) claim.")

        # Construct the dynamic issuer
        dynamic_issuer = f'https://sts.windows.net/{tenant_id}/'

        # Use the specified JWK_URL
        jwk_url = self.jwk_url

        # Fetch the public key from the JWK URL
        try:
            jwks_client = jwt.PyJWKClient(jwk_url)
            signing_key = jwks_client.get_signing_key_from_jwt(token).key
        except Exception as e:
            raise TokenError(f"Error fetching signing key: {str(e)}")

        # Now decode the token with verification, using the dynamic issuer
        try:
            decoded_token = jwt.decode(
                token,
                signing_key,
                algorithms=[self.algorithm],
                audience=self.audience,
                issuer=dynamic_issuer,
                options={
                    'verify_signature': verify,
                    'verify_exp': verify,
                    'verify_aud': self.audience is not None,
                },
            )
            return decoded_token
        except jwt.PyJWTError as e:
            raise TokenError(f"Token validation failed: {str(e)}")



class AzureAccessToken(AccessToken):
    def get_token_backend(self):
        return AzureTokenBackend(
            algorithm=settings.SIMPLE_JWT.get('ALGORITHM'),
            signing_key=settings.SIMPLE_JWT.get('SIGNING_KEY'),
            verifying_key=settings.SIMPLE_JWT.get('VERIFYING_KEY'),
            audience=settings.SIMPLE_JWT.get('AUDIENCE'),
            jwk_url=settings.SIMPLE_JWT.get('JWK_URL'),
            issuer=None,
        )



    def verify(self):
        # Inject 'id' from 'sub' for Azure B2C if missing
        if 'id' not in self.payload:
            self.payload['id'] = self.payload.get('sub', None)
            if self.payload['id'] is None:
                raise TokenError("Token has neither 'id' nor 'sub' field.")

        # Inject 'jti' if it's missing
        if 'jti' not in self.payload:
            self.payload['jti'] = self.payload['id']

        # Inject 'token_type' if missing
        if 'token_type' not in self.payload:
            self.payload['token_type'] = 'access'

        try:
            super().verify()
        except TokenError as e:
            raise TokenError(f"Token verification failed: {str(e)}")

class AzureJWTAuthentication(JWTAuthentication):
    def get_validated_token(self, raw_token):
        """
        Override token validation to handle Azure B2C's token structure.
        """
        try:
            validated_token = AzureAccessToken(raw_token)
            return validated_token
        except (InvalidToken, TokenError) as e:
            raise AuthenticationFailed(detail=str(e))



    def authenticate(self, request):
        """
        Authenticate the request using Azure B2C JWT tokens and map to Django User model.
        """
        raw_token = self.get_raw_token(self.get_header(request))

        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)

        # Get the token payload (Azure AD claims)
        payload = validated_token.payload

        # Map the claims to a Django User
        user = self.get_or_create_user_from_token(payload)

        return (user, validated_token)



    def get_or_create_user_from_token(self, payload):
        """
        Get or create a Django User instance from the Azure AD token claims.
        """
        user_uuid = payload.get('sub', None)
        if user_uuid is None:
            raise AuthenticationFailed("Token does not contain 'sub' claim.")

        user, created = User.objects.get_or_create(
            username=user_uuid,
            defaults = {
                "user_uuid":user_uuid
            }
        )
        return user
    




# Websocket authentication middleware
import os
import jwt
import requests
from django.conf import settings
from jwt.algorithms import RSAAlgorithm
from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
import json

class AzureJWTMiddleware(BaseMiddleware):
    def __init__(self, inner):
        self.inner = inner
        self.jwk_url = "https://login.microsoftonline.com/common/discovery/v2.0/keys"
        self.audience = f"api://{os.getenv('FRONTEND_DOMAIN')}/{os.getenv('AZURE_ENTRA_CLIENT_ID')}"
        super().__init__(inner)

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        query_params = parse_qs(query_string)
        access_token = query_params.get("access_token", [None])[0]

        if access_token is None:
            scope["user"] = AnonymousUser()
            return await self.inner(scope, receive, send)


        # Obtain public key from JWKs
        jwks = await self.get_jwks()
        unverified_header = jwt.get_unverified_header(access_token)
        rsa_key = {}
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"],
                }
        if not rsa_key:
            raise jwt.InvalidTokenError("Unable to find matching JWK.")

        public_key = RSAAlgorithm.from_jwk(json.dumps(rsa_key))



        # Dynamic Issuer
        unverified_payload = jwt.decode(access_token, options={"verify_signature": False})
        tenant_id = unverified_payload.get('tid')
        if not tenant_id:
            raise TokenError("Token does not contain 'tid' (tenant ID) claim.")
        dynamic_issuer = f'https://sts.windows.net/{tenant_id}/'



        # Decode and validate the token
        payload = jwt.decode(
            access_token,
            public_key, # Public key for signature verification
            algorithms=["RS256"],
            audience=self.audience,
            issuer=dynamic_issuer,
        )

        user = await self.get_or_create_user(payload)
        scope["user"] = user

        return await self.inner(scope, receive, send)

    @database_sync_to_async
    def get_or_create_user(self, payload):
        # Assuming the unique identifier is in 'sub' claim
        user, created = User.objects.get_or_create(
            username=payload.get("sub"),
            defaults={
                "user_uuid": payload.get("sub"),
                "email": payload.get("email", ""),
                "first_name": payload.get("given_name", ""),
                "last_name": payload.get("family_name", ""),
            },
        )
        return user

    @database_sync_to_async
    def get_jwks(self):
        response = requests.get(self.jwk_url)
        response.raise_for_status()
        return response.json()



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