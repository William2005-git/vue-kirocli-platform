from typing import Optional

from app.config import settings


def get_saml_settings() -> dict:
    idp_entity_id = settings.SAML_IDP_ENTITY_ID or ""
    idp_sso_url = settings.SAML_IDP_SSO_URL or ""
    idp_x509_cert = settings.SAML_IDP_X509_CERT or ""
    sp_entity_id = settings.SAML_SP_ENTITY_ID or ""
    sp_acs_url = settings.SAML_SP_ACS_URL or ""

    return {
        "strict": True,
        "debug": settings.DEBUG,
        "sp": {
            "entityId": sp_entity_id,
            "assertionConsumerService": {
                "url": sp_acs_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
            "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
            "x509cert": "",
            "privateKey": "",
        },
        "idp": {
            "entityId": idp_entity_id,
            "singleSignOnService": {
                "url": idp_sso_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "x509cert": idp_x509_cert,
        },
    }


def is_saml_configured() -> bool:
    return bool(
        settings.SAML_IDP_ENTITY_ID
        and settings.SAML_IDP_SSO_URL
        and settings.SAML_IDP_X509_CERT
        and settings.SAML_SP_ENTITY_ID
        and settings.SAML_SP_ACS_URL
    )


def parse_saml_attributes(attributes: dict) -> dict:
    def get_attr(key: str) -> Optional[str]:
        val = attributes.get(key)
        if val and isinstance(val, list):
            return val[0]
        return val

    username = (
        get_attr("http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name")
        or get_attr("username")
        or get_attr("UserName")
        or ""
    )
    email = (
        get_attr(
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress"
        )
        or get_attr("email")
        or get_attr("Email")
        or ""
    )
    full_name = (
        get_attr(
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/displayname"
        )
        or get_attr("displayName")
        or get_attr("FullName")
        or ""
    )

    groups_raw = attributes.get(
        "http://schemas.xmlsoap.org/claims/Group",
        attributes.get("groups", attributes.get("Groups", [])),
    )
    if isinstance(groups_raw, str):
        groups = [groups_raw]
    elif isinstance(groups_raw, list):
        groups = groups_raw
    else:
        groups = []

    return {
        "username": username,
        "email": email,
        "full_name": full_name,
        "groups": groups,
    }
