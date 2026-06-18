from pydantic import BaseModel, Field


class AccountProfileUpdate(BaseModel):
    """Fields a user may change about their own profile.

    Deliberately omits ``email`` (the login identity and worker-lookup key), ``roles``, and
    ``is_active`` so none of those can be self-edited through the account surface.
    """

    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None


class ChangePasswordRequest(BaseModel):
    """Payload for a self-service password change.

    ``current_password`` is verified before the new password is applied so a hijacked session
    cannot silently change the password.
    """

    current_password: str
    new_password: str = Field(min_length=8)
