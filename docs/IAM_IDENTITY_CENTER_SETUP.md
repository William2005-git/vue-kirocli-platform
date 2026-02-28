# AWS IAM Identity Center Configuration Guide

This guide provides detailed steps for configuring AWS IAM Identity Center for KiroCLI Platform. **Complete these steps BEFORE running the installation script**, as you'll need the configuration values during installation.

---

## Prerequisites

- AWS Account with IAM Identity Center enabled
- Administrator access to IAM Identity Center
- EC2 instance public IP or domain name

---

## Step 1: Enable IAM Identity Center

If you haven't enabled IAM Identity Center yet:

1. Open the AWS Console
2. Navigate to **IAM Identity Center** (formerly AWS SSO)
3. Click **Enable** if not already enabled
4. Choose your identity source:
   - **Identity Center directory** (recommended for getting started)
   - **Active Directory**
   - **External identity provider**

---

## Step 2: Create Users

1. In IAM Identity Center console, go to **Users**
2. Click **Add user**
3. Fill in user details:
   - **Username**: User's login name (e.g., `john.doe`)
   - **Email address**: User's email (required, used as Subject in SAML)
   - **First name**: User's first name
   - **Last name**: User's last name
   - **Display name**: Full name
4. Click **Next**
5. Choose group membership (optional, can be done later)
6. Click **Add user**
7. Repeat for all users who need access to KiroCLI Platform

> **Important**: The email address will be used as the SAML Subject attribute. Make sure it's valid and unique.

---

## Step 3: Create Groups

Groups allow you to manage permissions for multiple users at once.

1. In IAM Identity Center console, go to **Groups**
2. Click **Create group**
3. Enter group details:
   - **Group name**: Descriptive name (e.g., `KiroCLI-Admins`, `KiroCLI-Users`)
   - **Description**: Purpose of the group
4. Click **Create group**
5. Add users to the group:
   - Select the group
   - Click **Add users**
   - Select users from the list
   - Click **Add users**

### Recommended Groups

| Group Name | Description | Recommended Users |
|------------|-------------|-------------------|
| `KiroCLI-Admins` | Full platform access with admin privileges | Platform administrators |
| `KiroCLI-Users` | Standard user access | Regular users |
| `KiroCLI-ReadOnly` | Read-only access (if needed) | Auditors, viewers |

---

## Step 4: Create SAML Application

1. In IAM Identity Center console, go to **Applications**
2. Click **Add application**
3. Select **Add custom SAML 2.0 application**
4. Click **Next**

### Configure Application Details

1. **Display name**: `KiroCLI Platform` (or your preferred name)
2. **Description**: `Browser-based Kiro CLI terminal platform`
3. **Application start URL**: Leave empty (optional)
4. **Session duration**: `8 hours` (or your preferred duration)

### Configure Application Metadata

You need your EC2 public IP or domain name for these URLs.

**If using IP address**:
- Replace `<EC2_PUBLIC_IP>` with your actual EC2 public IP (e.g., `54.123.45.67`)

**If using domain name**:
- Replace `<EC2_PUBLIC_IP>` with your domain (e.g., `kirocli.example.com`)

| Field | Value |
|-------|-------|
| **Application ACS URL** | `http://<EC2_PUBLIC_IP>:3000/api/v1/auth/saml/callback` |
| **Application SAML audience** | `http://<EC2_PUBLIC_IP>:3000/api/v1/auth/saml/metadata` |

**Example with IP**:
- Application ACS URL: `http://54.123.45.67:3000/api/v1/auth/saml/callback`
- Application SAML audience: `http://54.123.45.67:3000/api/v1/auth/saml/metadata`

**Example with domain**:
- Application ACS URL: `http://kirocli.example.com:3000/api/v1/auth/saml/callback`
- Application SAML audience: `http://kirocli.example.com:3000/api/v1/auth/saml/metadata`

Click **Submit**.

---

## Step 5: Configure Attribute Mappings

After creating the application, configure attribute mappings:

1. In the application details page, go to **Attribute mappings** tab
2. Click **Add new attribute mapping** for each attribute below:

| User attribute in the application | Maps to this string value or user attribute in IAM Identity Center | Format |
|-----------------------------------|-------------------------------------------------------------------|--------|
| `Subject` | `${user:email}` | `emailAddress` |
| `email` | `${user:email}` | `unspecified` |
| `groups` | `${user:groups}` | `unspecified` |

### Detailed Steps for Each Attribute

**Attribute 1: Subject** (Required)
- User attribute in the application: `Subject`
- Maps to: `${user:email}`
- Format: `emailAddress`

> **Critical**: Subject MUST be `${user:email}` with format `emailAddress`. Using `${user:name}` will cause "No access" errors.

**Attribute 2: email** (Required)
- User attribute in the application: `email`
- Maps to: `${user:email}`
- Format: `unspecified`

**Attribute 3: groups** (Required)
- User attribute in the application: `groups`
- Maps to: `${user:groups}`
- Format: `unspecified`

Click **Save changes**.

---

## Step 6: Assign Users/Groups to Application

1. In the application details page, go to **Assigned users and groups** tab
2. Click **Assign users and groups**
3. Select the **Groups** tab (recommended) or **Users** tab
4. Select the groups or users you want to grant access
5. Click **Assign users** or **Assign groups**

### Recommended Assignment

- Assign groups rather than individual users for easier management
- Start with a small group for testing (e.g., 1-2 users)
- Expand access after verifying the platform works correctly

---

## Step 7: Collect Configuration Values

You'll need these values when running the installation script. **Write them down or keep this page open**.

### 7.1 SAML IDP Entity ID

1. In the application details page, go to **IAM Identity Center metadata** section
2. Copy the **IAM Identity Center SAML issuer URL**
3. Example: `https://portal.sso.cn-northwest-1.amazonaws.com/saml/assertion/ABCDEFGHIJK`

**Save this as**: `SAML_IDP_ENTITY_ID`

### 7.2 SAML IDP SSO URL

1. In the same **IAM Identity Center metadata** section
2. Copy the **IAM Identity Center sign-in URL**
3. Example: `https://portal.sso.cn-northwest-1.amazonaws.com/saml/assertion/ABCDEFGHIJK`

**Save this as**: `SAML_IDP_SSO_URL`

> **Note**: In many cases, the Entity ID and SSO URL are the same value.

### 7.3 SAML IDP X509 Certificate

1. In the same **IAM Identity Center metadata** section
2. Click **Download** next to **IAM Identity Center certificate**
3. Open the downloaded `.pem` file in a text editor
4. Copy the entire certificate content (including `-----BEGIN CERTIFICATE-----` and `-----END CERTIFICATE-----`)

**Save this as**: `SAML_IDP_X509_CERT`

**Example format**:
```
-----BEGIN CERTIFICATE-----
MIIDXTCCAkWgAwIBAgIJAKL0UG+mRKzBMA0GCSqGSIb3DQEBCwUAMEUxCzAJBgNV
BAYTAkFVMRMwEQYDVQQIDApTb21lLVN0YXRlMSEwHwYDVQQKDBhJbnRlcm5ldCBX
... (more lines) ...
-----END CERTIFICATE-----
```

### 7.4 IAM Identity Store ID

1. In IAM Identity Center console, go to **Settings**
2. Find **Identity source** section
3. Copy the **Identity store ID**
4. Example: `d-1234567890`

**Save this as**: `IAM_IDENTITY_STORE_ID`

### 7.5 AWS Region

The AWS region where your IAM Identity Center is configured.

**Common values**:
- China (Ningxia): `cn-northwest-1`
- China (Beijing): `cn-north-1`
- US East (N. Virginia): `us-east-1`
- US West (Oregon): `us-west-2`

**Save this as**: `AWS_REGION`

---

## Configuration Summary

Before running the installation script, you should have these values ready:

| Configuration Item | Example Value | Where to Use |
|-------------------|---------------|--------------|
| SAML_IDP_ENTITY_ID | `https://portal.sso.cn-northwest-1.amazonaws.com/saml/assertion/ABCDEFGHIJK` | Installation script prompt |
| SAML_IDP_SSO_URL | `https://portal.sso.cn-northwest-1.amazonaws.com/saml/assertion/ABCDEFGHIJK` | Installation script prompt |
| SAML_IDP_X509_CERT | `-----BEGIN CERTIFICATE-----...` | AWS Secrets Manager (after installation) |
| IAM_IDENTITY_STORE_ID | `d-1234567890` | Installation script prompt |
| AWS_REGION | `cn-northwest-1` | Installation script prompt |
| EC2_PUBLIC_IP or DOMAIN | `54.123.45.67` or `kirocli.example.com` | Installation script prompt |

---

## Verification

After completing these steps:

1. ✅ IAM Identity Center is enabled
2. ✅ Users are created with valid email addresses
3. ✅ Groups are created and users are assigned
4. ✅ SAML application is created with correct URLs
5. ✅ Attribute mappings are configured (Subject, email, groups)
6. ✅ Users/groups are assigned to the application
7. ✅ Configuration values are collected and ready

---

## Next Steps

Now you're ready to proceed with the installation:

1. [Install Kiro CLI](../README.md#installing-kiro-cli-required-before-deployment)
2. Clone the project code
3. Run the installation script (`./scripts/install.sh`)
4. Configure AWS Secrets Manager (post-installation)

---

## Troubleshooting

### "No access" error after login

**Cause**: Subject attribute is not configured correctly.

**Solution**: 
- Verify Subject mapping is `${user:email}` with format `emailAddress`
- Do NOT use `${user:name}` or any other attribute

### "Invalid response" error

**Cause**: Application URLs don't match the backend configuration.

**Solution**:
- Verify Application ACS URL matches `SAML_SP_ACS_URL` in backend `.env`
- Verify Application SAML audience matches `SAML_SP_ENTITY_ID` in backend `.env`
- Check for typos or extra characters (e.g., duplicated `https:`)

### Users can't see the application

**Cause**: Users/groups are not assigned to the application.

**Solution**:
- Go to application **Assigned users and groups** tab
- Assign the appropriate users or groups

### Certificate errors

**Cause**: X509 certificate is not properly formatted or copied.

**Solution**:
- Ensure certificate includes `-----BEGIN CERTIFICATE-----` and `-----END CERTIFICATE-----`
- No extra spaces or line breaks before/after the certificate
- Copy the entire certificate content from the downloaded `.pem` file

---

## Additional Resources

- [AWS IAM Identity Center Documentation](https://docs.aws.amazon.com/singlesignon/latest/userguide/what-is.html)
- [SAML 2.0 Configuration Guide](https://docs.aws.amazon.com/singlesignon/latest/userguide/samlapps.html)
- [KiroCLI Platform Deployment Guide](EC2_DEPLOYMENT_V1.1.md)
