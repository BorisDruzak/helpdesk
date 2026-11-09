import hashlib
from pathlib import Path

import pytest

from scripts.configure_helpdesk_staging_ola import enable_ola, main

pytestmark = pytest.mark.no_db


def test_enable_keeps_other_settings_and_exact_private_backup(tmp_path):
    path=tmp_path/'staging.env';before=b'EXAMPLE=preserved\nTICKET_OLA_ENABLED=false\n';path.write_bytes(before)
    result=enable_ola(path,expected_sha256=hashlib.sha256(before).hexdigest())
    assert path.read_bytes()==b'EXAMPLE=preserved\nTICKET_OLA_ENABLED=true\n'
    assert Path(result['backup']).read_bytes()==before
    assert not enable_ola(path,expected_sha256=result['environment_sha256'])['changed']


def test_stale_hash_and_symlink_rejected_without_write(tmp_path):
    path=tmp_path/'staging.env';path.write_text('EXAMPLE=preserved')
    with pytest.raises(ValueError,match='changed'):
        enable_ola(path,expected_sha256='0'*64)
    assert path.read_text()=='EXAMPLE=preserved'


def test_cli_cannot_target_production(monkeypatch):
    monkeypatch.setattr('socket.gethostname',lambda:'production')
    monkeypatch.setattr('sys.argv',['configure','--expected-release','abc','--apply','--expected-environment-sha256','0'*64])
    with pytest.raises(SystemExit,match='guard failed'):
        main()


def test_release_check_update_and_restart_share_deployment_lock(monkeypatch):
    from contextlib import contextmanager
    from scripts import configure_helpdesk_staging_ola as config
    active=[];steps=[]
    @contextmanager
    def lock():
        active.append(True)
        try: yield
        finally: active.pop()
    def checked(step, result=None):
        def call(*args, **kwargs):
            assert active
            steps.append(step)
            return result
        return call
    monkeypatch.setattr(config,'deployment_lock',lock,raising=False)
    monkeypatch.setattr(config,'require_staging_release',checked('release'),raising=False)
    monkeypatch.setattr(config,'enable_ola',checked('config',{'changed':True}))
    monkeypatch.setattr(config.subprocess,'run',checked('service'))
    config.apply_to_staging('a'*40,'b'*64)
    assert steps==['release','config','service','service']
