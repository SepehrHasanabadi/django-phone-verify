import pytest
from django.test import override_settings
from django.urls import reverse

from tests import test_settings
from conftest import sandbox_backends

PHONE_NUMBER = "+13478379634"
SECURITY_CODE = "123456"
SESSION_TOKEN = "phone-auth-session-token"

pytestmark = pytest.mark.django_db


def _get_backend_cls(backend):
    backend_import_path = backend.get("BACKEND")
    backend_cls = backend_import_path.split("phone_verify.backends.")[1]
    return backend_cls


def test_backends(client, mocker, backend):
    with override_settings(PHONE_VERIFICATION=backend):
        url = reverse("phone-register")
        phone_number = PHONE_NUMBER
        data = {"phone_number": phone_number}

        mocker.patch(
            "phone_verify.backends.base.BaseBackend.generate_session_token",
            return_value=SESSION_TOKEN,
        )
        mocker.patch(
            "phone_verify.backends.base.BaseBackend.generate_security_code",
            return_value=SECURITY_CODE,
        )
        message = "Welcome to Phone Verify! Please use security code 123456 to proceed."
        from_number = test_settings.DJANGO_SETTINGS["PHONE_VERIFICATION"]["OPTIONS"][
            "FROM"
        ]

        backend_cls = _get_backend_cls(backend)

        if (
            backend_cls == "nexmo.NexmoBackend"
            or backend_cls == "nexmo.NexmoSandboxBackend"
        ):
            # Mock the nexmo client
            mock_nexmo_send_message = mocker.patch(
                "phone_verify.backends.nexmo.nexmo.Client.send_message"
            )
            test_data = {"from": from_number, "to": phone_number, "text": message}
        elif (
            backend_cls == "twilio.TwilioBackend"
            or backend_cls == "twilio.TwilioSandboxBackend"
        ):
            # Mock the twilio client
            mock_twilio_send_message = mocker.patch(
                "phone_verify.backends.twilio.TwilioRestClient.messages"
            )
            mock_twilio_send_message.create = mocker.MagicMock()
        elif backend_cls == "kavenegar.KavenegarBackend":
            # Mock the Kavenegar client
            mock_kavenegar_send_message = mocker.patch(
                "phone_verify.backends.kavenegar.KavenegarAPI.sms_send"
            )
            test_data = {
                "receptor": phone_number,
                "message": message,
                "sender": from_number,
            }

        response = client.post(url, data)
        assert response.status_code == 200

        if backend_cls == "nexmo.NexmoBackend":
            mock_nexmo_send_message.assert_called_once_with(test_data)
        elif backend_cls == "twilio.TwilioBackend":
            mock_twilio_send_message.create.assert_called_once_with(
                to=phone_number, body=message, from_=from_number
            )
        elif backend_cls == "kavenegar.KavenegarBackend":
            mock_kavenegar_send_message.assert_called_once_with(test_data)

        # Get the last part of the backend and check if that is a Sandbox Backend
        if backend_cls in sandbox_backends:
            url = reverse("phone-verify")
            data = {
                "phone_number": phone_number,
                "session_token": SESSION_TOKEN,
                "security_code": SECURITY_CODE,
            }

            response = client.post(url, data)
            assert response.status_code == 200
            response_data = {"message": "Security code is valid."}
            assert response.data == response_data
