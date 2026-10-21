"""Commit request transactions before returning a response to Starlette.

Streaming handlers must explicitly commit before emitting their completion event;
the request dependency rolls back any remaining work when the stream closes.
"""
from fastapi import APIRouter as FastAPIRouter, Request
from fastapi.routing import APIRoute
from starlette.responses import StreamingResponse


class TransactionRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def transactional(request: Request):
            request.scope["transaction_route"] = True
            response = await handler(request)
            if isinstance(response, StreamingResponse):
                return response
            for session in request.scope.get("database_sessions", []):
                await session.commit()
            return response

        return transactional


class APIRouter(FastAPIRouter):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("route_class", TransactionRoute)
        super().__init__(*args, **kwargs)
