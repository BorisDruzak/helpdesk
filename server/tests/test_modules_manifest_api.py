import io
import json
import uuid
import zipfile
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from aiohttp import FormData
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, DeviceDesiredModule, DeviceModule, Module
from utils.module_builder import build_module_package
from utils.module_preflight import preflight_module_zip


@pytest.mark.asyncio
async def test_create_module_returns_manifest_v2(test_client):
    module_name = f"mod_{uuid.uuid4().hex[:8]}"
    response = await test_client.post('/api/modules/create', json={
        'module_name': module_name,
        'version': '1.0.0',
        'tool_name': 'ping',
        'method_name': 'do_ping',
        'description': 'Ping tool',
        'user_function_body': 'return {"ok": True}',
        'risk_level': 'safe_readonly',
        'platforms': ['any'],
        'metadata': {
            'domain': 'custom',
            'risk_level': 'safe_readonly',
            'requires_consent': False,
            'timeout_sec': 30,
            'idempotent': True,
            'allow_roles': ['admin'],
            'scopes': ['custom'],
        },
        'capabilities': [],
        'presets': [],
        'params_schema': [],
    })
    assert response.status == 200, await response.text()
    data = await response.json()
    assert data['status'] == 'success'
    assert data['manifest_version'] == 2
    assert data['validation_status'] == 'passed'
    assert data['tools_count'] == 1


@pytest.mark.asyncio
async def test_upload_legacy_manifest_returns_compat(test_client):
    module_name = f"legacy_{uuid.uuid4().hex[:8]}"
    manifest = {
        'module_name': module_name,
        'module_version': '0.1.0',
        'entrypoint': 'module:register',
        'description': 'Legacy module',
        'platforms': ['any'],
        'tools': [
            {
                'name': f'{module_name}.collect_activity',
                'description': 'Legacy collect tool',
            }
        ],
    }
    module_py = f'''from typing import Dict, Any
from modules.base_module import BaseCollector
from core.registry import exposed_tool

class _Collector(BaseCollector):
    @property
    def name(self) -> str:
        return "{module_name}"

    async def collect(self) -> Dict[str, Any]:
        return {{}}

    @exposed_tool(name="collect_activity", description="Legacy collect tool", risk_level="safe_readonly")
    async def collect_activity(self) -> Dict[str, Any]:
        return {{"ok": True}}

def register():
    return _Collector()
'''
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('manifest.json', json.dumps(manifest))
        zf.writestr('module.py', module_py)

    form = FormData()
    form.add_field('module_name', module_name)
    form.add_field('version', '0.1.0')
    form.add_field('file', buf.getvalue(), filename=f'{module_name}.zip', content_type='application/zip')
    response = await test_client.post('/api/modules/upload', data=form)
    assert response.status == 200, await response.text()
    data = await response.json()
    assert data['status'] == 'success'
    assert data['manifest_version'] == 1
    assert data['validation_status'] == 'compat'
    assert data['warnings']


@pytest.mark.asyncio
async def test_list_and_detail_include_manifest_metadata(test_client, test_engine):
    module_name = f"listed_{uuid.uuid4().hex[:8]}"
    zip_bytes, manifest_summary = build_module_package(
        module_name=module_name,
        version='1.2.3',
        tool_name='run',
        description='Listed module',
        user_function_body='return {"ok": True}',
        method_name='run_impl',
        metadata={'domain': 'listed', 'scopes': ['listed'], 'risk_level': 'safe_readonly'},
        platforms=['win32'],
    )
    ok, validation_json, manifest_json, manifest_summary = preflight_module_zip(zip_bytes)
    assert ok is True

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(Module(
            module_name=module_name,
            version='1.2.3',
            sha256=uuid.uuid4().hex + uuid.uuid4().hex,
            size=len(zip_bytes),
            storage_path=f'{module_name}/1.2.3/module.zip',
            uploaded_by='support',
            manifest_json=manifest_json,
            validation_json=validation_json,
            manifest_summary=manifest_summary,
        ))
        await session.commit()

    list_response = await test_client.get('/api/modules')
    assert list_response.status == 200
    list_data = await list_response.json()
    item = next(entry for entry in list_data['modules'] if entry['module_name'] == module_name)
    assert item['manifest_version'] == 2
    assert item['platforms'] == ['win32']
    assert item['tools_count'] == 1
    assert item['has_full_metadata'] is True

    detail_response = await test_client.get(f'/api/modules/{module_name}/1.2.3')
    assert detail_response.status == 200
    detail_data = await detail_response.json()
    assert detail_data['status'] == 'ok'
    assert detail_data['manifest_json']['tools'][0]['method'] == 'run_impl'
    assert detail_data['validation_json']['validation_status'] == 'passed'
    assert detail_data['tools'][0]['metadata']['domain'] == 'listed'


@pytest.mark.asyncio
async def test_rollback_updates_desired_state(test_client, test_engine):
    device_id = str(uuid.uuid4())
    module_name = f"rollback_{uuid.uuid4().hex[:8]}"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        session.add(Device(
            device_id=device_id,
            protocol_version='ws_ticket_v3',
            agent_version='1.0.0',
            hostname='rollback-host',
            os='linux',
            capabilities={},
            device_metadata={},
            first_seen_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
            last_handshake_at=datetime.now(timezone.utc),
        ))
        session.add(DeviceDesiredModule(
            device_id=device_id,
            module_name=module_name,
            desired_version='1.1.0',
            state='installed',
            reason='manual',
            updated_at=datetime.now(timezone.utc),
            updated_by='admin',
        ))
        await session.commit()

    async def fake_send_ws_command(**_kwargs):
        return {
            "payload": {
                "status": "success",
                "data": {
                    "observations": {
                        "rolled_back": module_name,
                        "active_path": f"/tmp/{module_name}/1.0.0",
                        "active_version": "1.0.0",
                    }
                },
            }
        }

    with patch('modules.handlers.send_ws_command', fake_send_ws_command):
        response = await test_client.post('/api/rollback_module', json={
            'device_id': device_id,
            'name': module_name,
            'actor_role': 'admin',
        })

    assert response.status == 200, await response.text()
    data = await response.json()
    assert data['status'] == 'success'
    assert data['data']['observations']['active_version'] == '1.0.0'

    async with session_maker() as session:
        desired = (
            await session.execute(
                select(DeviceDesiredModule).where(
                    DeviceDesiredModule.device_id == device_id,
                    DeviceDesiredModule.module_name == module_name,
                )
            )
        ).scalar_one()
        assert desired.desired_version == '1.0.0'
        assert desired.reason == 'manual_rollback'


@pytest.mark.asyncio
async def test_bulk_install_sets_desired_state_and_followup_sync(test_client, test_engine, tmp_path):
    device_id = str(uuid.uuid4())
    module_name = f"bulk_{uuid.uuid4().hex[:8]}"
    zip_bytes, manifest_summary = build_module_package(
        module_name=module_name,
        version='2.0.0',
        tool_name='run',
        description='Bulk install module',
        user_function_body='return {"ok": True}',
        method_name='run_impl',
        metadata={'domain': 'bulk', 'scopes': ['bulk'], 'risk_level': 'safe_readonly'},
        platforms=['linux'],
    )
    ok, validation_json, manifest_json, manifest_summary = preflight_module_zip(zip_bytes)
    assert ok is True

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(Device(
            device_id=device_id,
            protocol_version='ws_ticket_v3',
            agent_version='1.0.0',
            hostname='bulk-host',
            os='linux',
            capabilities={},
            device_metadata={},
            first_seen_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
            last_handshake_at=datetime.now(timezone.utc),
        ))
        session.add(Module(
            module_name=module_name,
            version='2.0.0',
            sha256=uuid.uuid4().hex + uuid.uuid4().hex,
            size=len(zip_bytes),
            storage_path=f'{module_name}/2.0.0/module.zip',
            uploaded_by='support',
            manifest_json=manifest_json,
            validation_json=validation_json,
            manifest_summary=manifest_summary,
        ))
        await session.commit()

    issued_commands = []

    async def fake_enqueue_command_async(**kwargs):
        issued_commands.append(kwargs["command"])
        return f'op-{len(issued_commands)}'

    with patch('modules.handlers.enqueue_command_async', fake_enqueue_command_async), \
         patch('modules.handlers.PolicyEngine.check_policy', return_value=SimpleNamespace(allow=True, reason=None, required_role=None)), \
         patch('modules.handlers.MODULES_STORAGE_DIR', tmp_path):
        module_path = tmp_path / module_name / '2.0.0' / 'module.zip'
        module_path.parent.mkdir(parents=True, exist_ok=True)
        module_path.write_bytes(zip_bytes)
        response = await test_client.post('/api/modules/bulk_install', json={
            'module_name': module_name,
            'version': '2.0.0',
            'device_ids': [device_id],
            'replace_if_exists': False,
        })

    assert response.status == 202, await response.text()
    data = await response.json()
    assert data['status'] == 'accepted'
    assert issued_commands == ['install_module_package', 'list_installed_modules', 'list_tools']

    async with session_maker() as session:
        desired = (
            await session.execute(
                select(DeviceDesiredModule).where(
                    DeviceDesiredModule.device_id == device_id,
                    DeviceDesiredModule.module_name == module_name,
                )
            )
        ).scalar_one()
        assert desired.state == 'installed'
        assert desired.desired_version == '2.0.0'
        assert desired.reason == 'manual'


@pytest.mark.asyncio
async def test_install_module_returns_conflict_when_archive_missing(test_client, test_engine):
    device_id = str(uuid.uuid4())
    module_name = f"missing_{uuid.uuid4().hex[:8]}"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        session.add(Device(
            device_id=device_id,
            protocol_version='ws_ticket_v3',
            agent_version='1.0.0',
            hostname='missing-host',
            os='linux',
            capabilities={},
            device_metadata={},
            first_seen_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
            last_handshake_at=datetime.now(timezone.utc),
        ))
        session.add(Module(
            module_name=module_name,
            version='1.0.0',
            sha256=uuid.uuid4().hex + uuid.uuid4().hex,
            size=1234,
            storage_path=f'{module_name}/1.0.0/module.zip',
            uploaded_by='support',
            manifest_json={'module_name': module_name, 'module_version': '1.0.0', 'platforms': ['linux']},
            validation_json={'validation_status': 'passed'},
            manifest_summary={'tools': []},
        ))
        await session.commit()

    issued_commands = []

    async def fake_enqueue_command_async(**kwargs):
        issued_commands.append(kwargs["command"])
        return f'op-{len(issued_commands)}'

    with patch('modules.handlers.enqueue_command_async', fake_enqueue_command_async), \
         patch('modules.handlers.PolicyEngine.check_policy', return_value=SimpleNamespace(allow=True, reason=None, required_role=None)):
        response = await test_client.post(f'/api/devices/{device_id}/modules/install', json={
            'module_name': module_name,
            'version': '1.0.0',
        })

    assert response.status == 409, await response.text()
    data = await response.json()
    assert data['status'] == 'error'
    assert data['error_code'] == 'MODULE_FILE_MISSING'
    assert issued_commands == []


@pytest.mark.asyncio
async def test_install_builtin_module_is_noop(test_client, test_engine):
    device_id = str(uuid.uuid4())
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        session.add(Device(
            device_id=device_id,
            protocol_version='ws_ticket_v3',
            agent_version='1.0.0',
            hostname='builtin-host',
            os='linux',
            capabilities={},
            device_metadata={},
            first_seen_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
            last_handshake_at=datetime.now(timezone.utc),
        ))
        await session.commit()

    issued_commands = []

    async def fake_enqueue_command_async(**kwargs):
        issued_commands.append(kwargs["command"])
        return f'op-{len(issued_commands)}'

    with patch('modules.handlers.enqueue_command_async', fake_enqueue_command_async), \
         patch('modules.handlers.PolicyEngine.check_policy', return_value=SimpleNamespace(allow=True, reason=None, required_role=None)):
        response = await test_client.post(f'/api/devices/{device_id}/modules/install', json={
            'module_name': 'screen',
            'version': '1.0.0',
        })

    assert response.status == 202, await response.text()
    data = await response.json()
    assert data['status'] == 'accepted'
    assert data['builtin'] is True
    assert str(data['operation_id']).startswith('builtin:')
    assert issued_commands == []


@pytest.mark.asyncio
async def test_bulk_install_builtin_module_is_noop(test_client, test_engine):
    device_id = str(uuid.uuid4())
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        session.add(Device(
            device_id=device_id,
            protocol_version='ws_ticket_v3',
            agent_version='1.0.0',
            hostname='builtin-bulk-host',
            os='linux',
            capabilities={},
            device_metadata={},
            first_seen_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
            last_handshake_at=datetime.now(timezone.utc),
        ))
        await session.commit()

    issued_commands = []

    async def fake_enqueue_command_async(**kwargs):
        issued_commands.append(kwargs["command"])
        return f'op-{len(issued_commands)}'

    with patch('modules.handlers.enqueue_command_async', fake_enqueue_command_async), \
         patch('modules.handlers.PolicyEngine.check_policy', return_value=SimpleNamespace(allow=True, reason=None, required_role=None)):
        response = await test_client.post('/api/modules/bulk_install', json={
            'module_name': 'screen',
            'version': '1.0.0',
            'device_ids': [device_id],
        })

    assert response.status == 202, await response.text()
    data = await response.json()
    assert data['status'] == 'accepted'
    assert data['builtin'] is True
    assert data['operations'] == []
    assert data['skipped'][0]['device_id'] == device_id
    assert issued_commands == []


@pytest.mark.asyncio
async def test_remove_last_version_marks_desired_absent(test_client, test_engine):
    device_id = str(uuid.uuid4())
    module_name = f"remove_{uuid.uuid4().hex[:8]}"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        session.add(Device(
            device_id=device_id,
            protocol_version='ws_ticket_v3',
            agent_version='1.0.0',
            hostname='remove-host',
            os='linux',
            capabilities={},
            device_metadata={},
            first_seen_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
            last_handshake_at=datetime.now(timezone.utc),
        ))
        session.add(DeviceModule(
            device_id=device_id,
            module_name=module_name,
            version='1.0.0',
            installed=True,
            active=False,
            state='installed',
            source='event',
            last_seen_at=datetime.now(timezone.utc),
        ))
        session.add(DeviceDesiredModule(
            device_id=device_id,
            module_name=module_name,
            desired_version='1.0.0',
            state='installed',
            reason='manual_rollback',
            updated_at=datetime.now(timezone.utc),
            updated_by='admin',
        ))
        await session.commit()

    issued_commands = []

    async def fake_enqueue_command_async(**kwargs):
        issued_commands.append(kwargs["command"])
        return f'op-{len(issued_commands)}'

    response = None
    with patch('modules.handlers.enqueue_command_async', fake_enqueue_command_async):
        response = await test_client.post(f'/api/devices/{device_id}/modules/remove_version', json={
            'module_name': module_name,
            'version': '1.0.0',
            'actor_role': 'admin',
        })

    assert response is not None
    assert response.status == 202, await response.text()
    data = await response.json()
    assert data['status'] == 'accepted'
    assert issued_commands == ['remove_module_version', 'list_installed_modules', 'list_tools']

    async with session_maker() as session:
        desired = (
            await session.execute(
                select(DeviceDesiredModule).where(
                    DeviceDesiredModule.device_id == device_id,
                    DeviceDesiredModule.module_name == module_name,
                )
            )
        ).scalar_one()
        assert desired.state == 'absent'
        assert desired.desired_version is None
        assert desired.reason == 'manual_remove'
