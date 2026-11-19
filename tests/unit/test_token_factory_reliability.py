import time

import httpx
import pytest

from ai.token_factory import TokenFactoryClient, TokenFactoryError


def completion(content, finish_reason='stop', **message_fields):
    return httpx.Response(200, json={'choices': [{
        'finish_reason': finish_reason, 'message': {'content': content, **message_fields},
    }]})


def client(handler):
    return TokenFactoryClient(api_key='dummy', base_url='https://factory.invalid/v1',
                              transport=httpx.MockTransport(handler))


@pytest.mark.parametrize('failure,reason', [
    (httpx.Response(408), '408'), (httpx.Response(429), '429'),
    (httpx.Response(500), '500'), (httpx.Response(502), '502'),
    (httpx.Response(503), '503'), (httpx.Response(504), '504'),
    (httpx.ReadTimeout('private request details'), 'timed out'),
    (httpx.RemoteProtocolError('private request details'), 'connection'),
])
def test_transient_failures_back_off_and_stop(monkeypatch, failure, reason):
    sleeps, requests = [], []
    monkeypatch.setattr(time, 'sleep', sleeps.append)

    def fail(request):
        requests.append(request.content)
        if isinstance(failure, Exception):
            raise failure
        return failure

    with client(fail) as api, pytest.raises(TokenFactoryError) as error:
        api.chat(model='test-model', messages=[])
    assert reason in str(error.value) and '3 attempts' in str(error.value)
    assert 'private' not in str(error.value)
    assert len(requests) == 3 and len(set(requests)) == 1
    assert len(sleeps) == 2 and 0 < sleeps[0] < sleeps[1] <= 5


@pytest.mark.parametrize('status', [400, 401, 403, 404, 422, 501])
def test_permanent_http_errors_are_not_retried(status, monkeypatch):
    monkeypatch.setattr(time, 'sleep', lambda _: pytest.fail('unexpected backoff'))
    calls = []

    def fail(request):
        calls.append(request)
        return httpx.Response(status, text='private provider body')

    with client(fail) as api, pytest.raises(TokenFactoryError, match=str(status)) as error:
        api.chat(model='test-model', messages=[])
    assert 'private' not in str(error.value) and len(calls) == 1
