# -*- coding: utf-8 -*-
from app.api.routers.admin_ops import router


def test_admin_ops_exposes_core_routes():
    paths = {getattr(r, "path", None) for r in router.routes}
    assert "/fix-db-schema" in paths
    assert "/system_logs/actions" in paths
    assert "/system_logs/ui" in paths
    assert "/admin/runtime-logs/files" in paths
    assert "/admin/runtime-logs/view" in paths
    assert "/admin/storage-usage" in paths
    assert "/admin/storage-usage/expired" in paths
    assert "/admin/storage-usage/orphan" in paths
    assert "/admin/payment-config" in paths
    assert "/admin/smtp-config" in paths
    assert "/admin/smtp-config/test" in paths
    assert "/admin/smtp-config/broadcast" in paths
    assert "/admin/maintenance-status" in paths
    assert "/admin/maintenance-config" in paths


def test_admin_ops_schemas_importable():
    from app.schemas.admin_ops import PaymentConfig, MaintenanceStatusOut, GenericMessageOut

    assert PaymentConfig(use_mock=True).use_mock is True
    assert MaintenanceStatusOut().is_active is False
    assert GenericMessageOut(message="ok").message == "ok"


def test_maintenance_status_service_standalone():
    from app.services.maintenance_status import (
        _default_maintenance_status_payload,
        _build_maintenance_status_payload,
        _get_login_maintenance_status_cached,
    )

    default = _default_maintenance_status_payload()
    assert default["enabled"] is False
    built = _build_maintenance_status_payload({"enabled": False, "message": "x"})
    assert built["message"] == "x"
    cached = _get_login_maintenance_status_cached()
    assert "is_active" in cached


def test_auth_login_uses_maintenance_service_not_endpoints():
    import inspect
    from app.services import auth_login

    src = inspect.getsource(auth_login._get_login_maintenance_status_cached)
    assert "maintenance_status" in src
    assert "endpoints" not in src
