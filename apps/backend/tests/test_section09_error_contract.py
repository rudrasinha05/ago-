import pytest
from fastapi import HTTPException

from ago.api_knowledge import storage_error


def test_authorization_error_never_becomes_storage_outage():
    with pytest.raises(HTTPException) as denied:
        storage_error(PermissionError('Memory permission required'))
    assert denied.value.status_code == 403
    with pytest.raises(HTTPException) as unavailable:
        storage_error(OSError('Private storage path must not leak'))
    assert unavailable.value.status_code == 503
    assert 'Private storage path' not in str(unavailable.value.detail)
