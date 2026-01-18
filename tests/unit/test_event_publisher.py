from types import SimpleNamespace
import app.care_sessions.event_publisher as ep


def test_publish_calls_publisher(monkeypatch):
    captured = []

    def fake_publish(**kwargs):
        captured.append(kwargs)

    # Monkeypatch the module-level publisher that event_publisher imports
    monkeypatch.setattr(ep, "publish_care_session_event", fake_publish)

    session = SimpleNamespace(
        id="11111111-1111-1111-1111-111111111111",
        patient_id="22222222-2222-2222-2222-222222222222",
        caregiver_id="33333333-3333-3333-3333-333333333333",
        check_in_time=None,
        check_out_time=None,
        status="in_progress",
        caregiver_notes=None,
    )

    pub = ep.SessionEventPublisher("test_schema")
    pub.publish_session_created(session)

    assert len(captured) == 1
    payload = captured[0]
    assert payload["event_type"] == "session.created"
    assert payload["tenant_schema"] == "test_schema"
    assert payload["session_data"]["id"] == str(session.id)
