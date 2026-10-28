"""A missing handoff is normal; an invalid supplied credential is not."""
from unittest.mock import Mock

import pytest
from fastapi import HTTPException, Request, Response

from ago.api_m2 import sso_session
from ago.security import AuthenticationError


def test_empty_handoff_is_no_content_and_does_not_redeem_credentials():
    repositories = Mock()
    request = Request({'type': 'http', 'headers': []})
    response = sso_session(request, Response(), db=None, repositories=repositories)
    assert response.status_code == 204
    assert response.body == b''
    assert response.headers['cache-control'] == 'no-store'
    repositories.resolve.assert_not_called()


def test_supplied_invalid_handoff_still_rejects_authentication():
    repositories = Mock()
    repositories.resolve.return_value.redeem_handoff.side_effect = AuthenticationError('Invalid')
    request = Request({'type': 'http', 'headers': [
        (b'cookie', b'ago_sso_result=untrusted; ago_sso_browser=untrusted')]})
    with pytest.raises(HTTPException) as error:
        sso_session(request, Response(), db=None, repositories=repositories)
    assert error.value.status_code == 401
