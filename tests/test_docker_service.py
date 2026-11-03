"""Verify the backend used inside Compose without needing Docker installed."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from threading import Thread
from http.server import ThreadingHTTPServer
from urllib.request import urlopen
from urllib.error import HTTPError
import json
import pytest


def test_backend_http_server_local():
    source = Path(__file__).resolve().parents[1] / 'infra/backend/server.py'
    spec = spec_from_file_location('proofops_disposable_backend', source)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    server = ThreadingHTTPServer(('127.0.0.1', 0), module.Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        for endpoint in ('/', '/health'):
            with urlopen(f'http://127.0.0.1:{port}{endpoint}', timeout=2) as response:
                body = json.load(response)
                assert response.status == 200
                assert body == {'status': 'ok', 'backend': module.BACKEND}
                assert response.headers['Cache-Control'] == 'no-store'
        with pytest.raises(HTTPError) as error:
            urlopen(f'http://127.0.0.1:{port}/private', timeout=2)
        assert error.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_dns_and_nginx_files_render(tmp_path):
    from proofops.real_lab import ComposeStack
    from test_real_lab import FakeDockerRunner
    stack = ComposeStack(tmp_path, 'proofops-a-123456abcd', 120, FakeDockerRunner())
    stack.init_files({'dns_target':'edge', 'proxy_target':'backend-a', 'backend_a_running':True})
    assert (stack.stack_dir/'dns/hosts').read_text().strip() == '10.223.120.10 app.proofops.test'
    nginx = (stack.stack_dir/'nginx/default.conf').read_text()
    assert 'proxy_pass http://10.223.120.21:8080;' in nginx
    stack.run('up', '-d')  # Register this isolated project in the fake runner.
    stack.set_dns('wrong')
    stack.set_proxy('backend-b')
    assert (stack.stack_dir/'dns/hosts').read_text().startswith('10.223.120.99 ')
    assert 'proxy_pass http://10.223.120.22:8080;' in (stack.stack_dir/'nginx/default.conf').read_text()
