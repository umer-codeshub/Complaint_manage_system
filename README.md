# AI Complaint Resolution Agent

A portfolio-quality **single-operator educational demonstration** built with **Python, Streamlit, CrewAI, Groq, a fictional CSV store, JSON policies, Pydantic, Google OAuth 2.0, and the official Gmail API**.

> **Not an online shop / not production-ready.** All customer orders, names, email addresses, and policies are invented. `example.com` demo addresses cannot be used as real customer inboxes. Never upload real customer information to a public deployment. This app does not process refunds, change orders, or confirm email delivery. This code has been validated by offline mocked tests; live Gmail and Groq integrations require your credentials and testing.

## Architecture: who is allowed to do what?

```text
Operator password gate
       |
Streamlit complaint form (Pydantic input validation)
       |
Python deterministic order lookup (fictional CSV, email match)
       |
CrewAI Complaint Analyst → Groq (structured triage, Pydantic validation)
       |                ↳ missing key / error => conservative rule-based fallback, clearly labeled
Python deterministic policy lookup (JSON)
       |
Python deterministic decision engine → recommend / request info / escalate
       |
CrewAI Customer Communication Drafter → Groq (structured subject/body)
       |                ↳ failed / offline => clearly labeled conservative template
Atomic local JSON ticket with UUID (DRAFT, never sends on creation)
       |
Operator reviews recipient + subject + editable body
       |
Explicit approval checkbox + optional separate test-recipient confirmation
       |
Gmail OAuth 2.0 (only `gmail.send`) → users.messages.send
       |
Ticket SUBMITTED with Gmail message ID, or UNKNOWN and send-locked for manual reconciliation
```

**Trust boundary:** CrewAI may classify complaints and compose *drafts*, but cannot access credentials, perform refunds, modify orders, or invoke Gmail. Order/policy reference data is fetched deterministically by Python. The approval service, not the AI, controls all Gmail submissions.

### Project folders

```text
app.py                           Streamlit UI, access gate and OAuth callback
agents/schemas.py                Pydantic schemas for intake and AI responses
agents/tasks.py                  Delimited prompts with untrusted complaint text
agents/crew.py                   Two CrewAI tasks using Groq (no external side effects)
agents/decision.py               Deterministic severity, refund & escalation logic
tools/order_lookup.py            Fictional CSV verification, email/ID comparison
tools/policy_lookup.py           Approved JSON policy lookup
tools/ticket_generator.py        Atomic JSON tickets with UUIDs and file lock
tools/gmail_sender.py            Gmail MIME + base64url encoding + API sender
auth/google_oauth.py             Web-app OAuth, signed one-use CSRF state, refreshable credentials
services/complaint_service.py    Orchestrates verification / analysis / decisions / tickets
services/email_approval.py       Server-side approval, send locking, statuses
data/sample_orders.csv           Ten fictional example orders
data/company_policies.json       Nine fictional, actionable policy categories
outputs/                         Private, ephemeral demo tickets and OAuth state digests
tests/                           Forty-six+ offline tests with mocked AI and Gmail
.streamlit/config.toml           Dashboard appearance
.streamlit/secrets.toml.example  Safe configuration template, **not** a credential file
```

## 1. Local setup (macOS / Linux)

**Recommended Python: 3.11.** Dependencies have not been installed or live-tested in the project author's sandbox because its Python environment cannot reach the package index. Official interface references are linked below. If you see a version-resolution error, choose Python 3.11 before changing packages.

```bash
unzip ai-complaint-resolution-agent.zip
cd ai-complaint-resolution-agent
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with **your own** Groq key, a strong operator password, a random state-signing secret, and your Google OAuth Web Application credentials. To make a random signing secret:

```bash
python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Never commit `.env` or `.streamlit/secrets.toml` to GitHub. For a local OAuth callback using `http://localhost:8501/`, launch as follows (this allowance is only for localhost):

```bash
export OAUTHLIB_INSECURE_TRANSPORT=1
python -m pytest -q
python -m streamlit run app.py
```

For other environments, HTTPS is mandatory. Streamlit opens at `http://localhost:8501/` for local use. **Operator password must be at least 12 characters**, and `OAUTH_STATE_SECRET` at least 32 characters.

## 2. Groq setup and testing

1. Sign up at <https://console.groq.com/> and create a Groq API key.
2. Set `GROQ_API_KEY` in `.env` locally or Streamlit Secrets in the cloud.
3. Use `GROQ_MODEL = "openai/gpt-oss-120b"`. CrewAI internally prefixes `groq/`, yielding `groq/openai/gpt-oss-120b` (LiteLLM provider syntax).
4. Run the app and click **Analyze complaint and create ticket**.
5. `ai_analysis_completed: true` on the ticket indicates the CrewAI structured analysis was returned and validated. When unavailable, the UI shows **NOT a live CrewAI/Groq analysis**.

Do **not** use `llama-3.3-70b-versatile` for free/developer accounts: Groq's deprecation page says it was removed there on August 16, 2026. Check <https://console.groq.com/docs/models> and <https://console.groq.com/docs/deprecations> for changes.

## 3. Google Cloud setup (Gmail API, Web Application OAuth)

The app requests **only** `https://www.googleapis.com/auth/gmail.send` and **does not read inbox messages**.

1. Open <https://console.cloud.google.com/>. Create or select a Google Cloud project.
2. **APIs & Services → Library**: search for **Gmail API** and select **Enable**.
3. Open **Google Auth Platform → Branding**; configure application name, support email and contact email. The interface may also call this **OAuth consent screen**.
4. Under **Audience**, choose **External** for a personal Gmail account; leave **Testing** enabled initially. Under **Test users**, add the specific Google account you will connect. Google Workspace organizations can use **Internal** when applicable.
5. Under **Data Access**, **Add or remove scopes** and choose/add: `https://www.googleapis.com/auth/gmail.send`. Save it. Do not add `gmail.readonly` / `gmail.modify` or broader scopes.
6. Under **Clients** (or **APIs & Services → Credentials → Create Credentials → OAuth client ID**) choose **Web application**. Do **not** choose Desktop app.
7. Under **Authorized redirect URIs**, add the **exact** URL below, including the trailing slash:

   ```text
   https://complaintmanagesystem-2v.streamlit.app/
   ```

8. Save. Copy the new **Client ID** and **Client Secret** to private Streamlit Secrets. Do not upload the OAuth client JSON to GitHub.
9. On the deployed app, enter your **operator password**, click **Connect Gmail**, then **Continue to Google authorization**. Google opens a new tab. Pick the authorized test user and approve the `gmail.send` permission.
10. Google redirects to the app, where you'll be asked to **unlock the dashboard again**. This is expected: Streamlit may start a new browser session after OAuth. The signed state and a server-side one-use nonce registry validate the return. Once unlocked, Gmail should show **Connected** in the redirected tab. Use **that tab** to approve and send.

**Security details:** OAuth signing requires a long `OAUTH_STATE_SECRET`; a hash of each pending state is kept in temporary private server storage for 10 minutes and consumed once; no access/refresh tokens are written to disk. Credentials are held in the current, password-unlocked Streamlit session only. App users cannot use session-state login as multi-user authentication. Google may expire/restrict test-mode credentials, and publishing an external public app may require Google app verification. This is intentionally a single-operator learning demonstration, not public authorization infrastructure.

**Google account status:** The app displays connected/disconnected, not the sending account's email identity, because reading profile data can require more authorization than the send-only scope. Disconnect clears the current app session; revoke Google's app permission separately via your Google Account for full revocation.

## 4. Streamlit Secrets (deployed app)

Open [Streamlit Community Cloud](https://share.streamlit.io/), select your app → **Settings → Secrets** (or during first deployment, **Advanced settings → Secrets**). Paste with real values:

```toml
GROQ_API_KEY = "gsk_your_private_key_here"
GROQ_MODEL = "openai/gpt-oss-120b"
OPERATOR_PASSWORD = "your_private_long_operator_password"
OAUTH_STATE_SECRET = "your_random_secret_at_least_32_characters"
GOOGLE_CLIENT_ID = "your_google_client_id.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "your_google_oauth_client_secret"
GOOGLE_REDIRECT_URI = "https://complaintmanagesystem-2v.streamlit.app/"
```

**The URL must match Google Cloud's Authorized redirect URI exactly.** Never share actual Secrets values in screenshots, public logs, or chat messages. Do not include a real `secrets.toml` in the repository.

## 5. GitHub upload and Community Cloud deployment

At GitHub create a **private** repository first (recommended). From the extracted project root:

```bash
git init
git add .
git status --short
git commit -m "Build AI complaint resolution agent with Gmail OAuth"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

You must authenticate using GitHub's supported credential method (e.g., Git Credential Manager or SSH); do not put personal-access tokens in repo files. Verify that `.env` and `.streamlit/secrets.toml` **do not** appear in `git status --short` or GitHub.

Go to <https://share.streamlit.io/> → **Create app** → choose the repository and `main` branch, set **Main file path** to `app.py`, and choose Python **3.11** in advanced settings if offered. Add Streamlit Secrets shown above, deploy, then check Logs. The user-specified URL `https://complaintmanagesystem-2v.streamlit.app/` will only belong to the app if your deployment already owns that subdomain.

**On macOS Finder:** hidden `.streamlit`, `.env.example`, and `.gitignore` files can be shown using **Command + Shift + .**. When uploading through GitHub's browser, ensure hidden files and directories are included. With `git add .`, they will be included automatically except ignored secret files. In the GitHub root, `app.py`, `requirements.txt`, `data/`, `agents/`, `tools/`, `auth/`, `services/`, `.streamlit/`, and `tests/` should be visible; don't upload the ZIP as a single file and expect Streamlit to extract it.

## 6. Safe demonstration tests

**Example 1: Late delivery and ignored support**

```text
Name: Ayesha Khan
Email: ayesha@example.com
Order ID: DEMO-1001
Complaint: My parcel is ten days late. I contacted support twice but received no response.
```

Expected: demo order verified, policy `P-001` loaded, human escalation recommended, ticket created, email remains `DRAFT`.

**Example 2: Damaged product:** `ali@example.com`, `DEMO-1002` — should request photos/details and human review, not approve a refund.

**Example 3: Refund outside window:** `sana@example.com`, `DEMO-1003` — past the demo policy's 14-day window, requiring escalation.

**Example 4: Invalid order ID:** `ayesha@example.com`, `INVALID-ID` — do not reveal order data; request additional information.

**Example 5: Prompt injection:** use the built-in example attempting to request API credentials; the AI should regard it as complaint text, not an instruction. There is no send action in the complaint workflow.

**To test a real Gmail send:** First complete OAuth using your own test Google account. Analyze a fictional ticket. In **Send Approved Draft via Gmail**, replace the example.com recipient with **an email address you control**, check **I confirm a different recipient is my authorized test email**, edit and review the draft, check the approval checkbox, then click **Approve & Send via Gmail** once. A successful call records Gmail's message ID and `SUBMITTED`, *not delivered*. Check Sent and Inbox manually. Do not send example data to strangers.

## 7. Delivery and idempotency cautions

- There are no automatic emails. Clicking Analyze never calls Gmail.
- The app writes `SENDING` to the ticket **before** calling Gmail. Duplicate button clicks from the app are blocked by a file lock and a ticket-state check.
- If Gmail returns a successful message ID, the ticket becomes `SUBMITTED`. That means the API accepted it, **not** that the email was delivered to an inbox.
- After an ambiguous timeout/network failure, the ticket becomes `UNKNOWN`; **do not retry** until someone checks Gmail Sent and manually reconciles the ticket.
- Gmail `messages.send` does not provide a guaranteed general-purpose idempotency key. If the server crashes between Gmail acceptance and ticket update, this demo locks the ticket at `SENDING` to avoid an automatic duplicate.
- Real production delivery guarantees require a durable transactional outbox / job system, provider-specific reconciliation, and controlled retry policy.

## 8. Troubleshooting

| Symptom | Likely cause / action |
|---|---|
| `ModuleNotFoundError` | Ensure Python 3.11 venv is active and run `pip install -r requirements.txt`. |
| Streamlit Cloud `No module named crewai` | Verify root `requirements.txt` and successful dependency build logs; select supported Python version. |
| Groq `401` | Wrong or missing `GROQ_API_KEY`; never paste the key into support messages. |
| Groq `model_not_found` | Check `openai/gpt-oss-120b` against Groq's current catalog and your plan/region. |
| CrewAI import/model error | Check `crewai[litellm]` installed; Groq requires its LiteLLM adapter. |
| **Connect Gmail** disabled | Missing Google OAuth settings or state secret in Cloud Secrets. |
| `redirect_uri_mismatch` / Error 400 | URI **exactly** `https://complaintmanagesystem-2v.streamlit.app/` in both Google Cloud and Secrets, including slash and scheme; ensure correct OAuth client. |
| `access_denied` / app in Testing | Add the Google account to the **Test users** list under Audience. |
| OAuth invalid/expired state | Complete within ten minutes using the returned tab. Reconnect after a restart or repeated callback. Do not reuse old OAuth links. |
| Authorization succeeds but disconnected in original tab | Expected with new Streamlit session. Unlock the *redirected* tab and use it to send. |
| OAuth callback code shown in URL briefly | App clears `code`/`state` after unlocking and processing. Don't share callback URLs or screenshots with codes. |
| `insufficientPermissions` / Gmail 403 | Enable Gmail API, select only `gmail.send` under Data Access, reconnect to re-authorize, and verify sender account. |
| Email status `UNKNOWN` or `SENDING` | Check Gmail Sent manually before attempting any further action. Never reset a ticket status blindly. |
| Ticket history disappeared | Community Cloud's local filesystem is **ephemeral** and can be replaced on restart/redeploy. Use Supabase/PostgreSQL in real projects. |
| Dashboard asks for operator password after Google returns | By design; the new tab is a different session. Authenticate again to finish OAuth. |

**Do not test the system by uploading real users' complaints or sending mail to unknown recipients.**

## 9. Security, operations, and production limitations

- One password-gated operator only; sharing the operator password grants access to demo tickets and connected actions. Streamlit session state is **not** secure multi-user identity. A public or multi-user app requires an external identity provider, role-based authorization, audit trails, private tenant-separated database, CSRF/session protection, rate limiting, and persistent session/token protection.
- All fictional sample records are included in version control. `outputs/` is ignored; locally generated tickets may contain complaint text and email addresses. Community Cloud storage is not durable and must not be used for real customer records.
- Store production refresh tokens in encrypted restricted storage, not Streamlit state or JSON. OAuth state digest registry must be made durable and distributed for multiple replicas.
- Service errors use generic correlation categories in app logs; secrets, complaint body, Gmail OAuth code, refresh token, and email address are not intentionally logged by app code. If an external library emits verbose logs, configure its logging before processing real data.
- The sample uses heuristic plus LLM triage; LLM output should always be manually reviewed. Policy interpretation and real compensation decisions require human authorization.
- A live AI response may contain mistakes despite structured validation; never treat the draft as a legally binding determination.
- To add real integrations later: implement authenticated order-database access, durable Postgres/Supabase ticket storage, an OAuth authorization server, customer consent controls, audit logs, and monitored async sending.

## 10. Test suite

```bash
python -m pytest -q
```

Tests mock the AI inference and Gmail network side effects. They cover order validation, missing policy, delayed order and repeated complaints, damage, refund window, critical severity, prompt injection attempts, token configuration, OAuth signature/state replay, permission errors, recipient validation, no email approval, duplicate send rejection, ambiguous send failures, ticket updates, and no auto-send during intake.

*Offline validation executed in the project author's environment: 46 tests passed. Live service integrations and full Streamlit runtime were not executed there because external credentials and dependency-index network access were unavailable.*

### Official interface and policy references

- CrewAI LLM/Groq/LiteLLM: <https://docs.crewai.com/en/concepts/llms>
- CrewAI structured `Task.output_pydantic`: <https://docs.crewai.com/en/concepts/tasks>
- Groq models: <https://console.groq.com/docs/models>
- Groq deprecations: <https://console.groq.com/docs/deprecations>
- Google OAuth Web Server apps: <https://developers.google.com/identity/protocols/oauth2/web-server>
- Gmail send: <https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/send>
- Streamlit Secrets: <https://docs.streamlit.io/deploy/concepts/secrets>

**Built for learning, demos, and portfolio presentation — human approval is required before sending anything.**
