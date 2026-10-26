"""Units deny sockets; explicit integration allows only dedicated loopback ports."""
import socket
import asyncio
import os

import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch, request):
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_create = socket.create_connection
    original_resolve = socket.getaddrinfo

    def blocked(*args, **kwargs):
        raise AssertionError("external_network_forbidden_in_validation_tests")

    integration = request.node.get_closest_marker("integration") and os.environ.get("LATHER_INTEGRATION_CONFIG")
    def allowed(address):
        return isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"} and address[1] in {57421, 57422}

    def connect(sock, address):
        return original_connect(sock, address) if integration and allowed(address) else blocked()

    def connect_ex(sock, address):
        return original_connect_ex(sock, address) if integration and allowed(address) else blocked()

    def create(address, *args, **kwargs):
        return original_create(address, *args, **kwargs) if integration and allowed(address) else blocked()

    def resolve(host, port, *args, **kwargs):
        return original_resolve(host, port, *args, **kwargs) if integration and allowed((host, port)) else blocked()

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "create_connection", create)
    monkeypatch.setattr(socket, "getaddrinfo", resolve)


@pytest.fixture(scope="session")
def integration_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
