# JustCall Integration for Frappe Helpdesk

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Frappe app that integrates [JustCall.io](https://justcall.io) with Frappe Helpdesk, enabling click-to-call functionality and automatic call logging.

## Features

- **Call via JustCall**: Call customers directly from Helpdesk tickets with pre-filled numbers
- **Standby via JustCall**: Open blank dialer to receive incoming calls
- **Automatic Call Logging**: All calls are logged to TP Call Log via webhooks
- **Smart Linking**: Outgoing calls from Helpdesk are auto-linked to tickets via metadata
- **Manual Linking**: Link incoming/external calls to tickets via "Link Call Log to this Ticket"
- **Recording Playback**: Play call recordings directly from the linking modal

## Requirements

- Frappe Framework v15+
- Frappe Helpdesk app
- Frappe Telephony app

## Installation

```bash
# Get the app
bench get-app https://github.com/your-org/justcall_integration.git

# Install on your site
bench --site your-site.com install-app justcall_integration

# Migrate to load fixtures
bench --site your-site.com migrate
```

## Configuration

### 1. JustCall Webhook Setup

1. Log in to your [JustCall account](https://justcall.io)
2. Go to **Profile → API & Webhooks → Webhook Settings**
3. Add a webhook for the **`call.completed`** event:
   
   ```
   https://your-site.com/api/method/justcall_integration.api.handle_call_webhook
   ```

4. Save the webhook configuration

### 2. Verify Fixtures

After installation, verify these fixtures are created:

- **Custom Field**: `HD Ticket.via_justcall` (Check field)
- **HD Form Script**: "JustCall Integration" (buttons on ticket form)
- **Property Setter**: `TP Call Log.recording_url` (changed to Long Text field)

## Usage

### Making Outgoing Calls

1. Open any HD Ticket in Helpdesk
2. Click the **"Call via JustCall"** button (solid blue button)
3. JustCall dialer opens in a new tab with the contact's phone pre-filled
4. Make your call
5. After the call ends, it automatically appears linked to the ticket

### Standby Mode for Incoming Calls

1. Open any HD Ticket in Helpdesk
2. Click the **"Standby via JustCall"** button (outline gray button)
3. JustCall dialer opens without any pre-filled number
4. You are now on standby - the dialer will ring when calls come in
5. After handling the call, it will be logged in TP Call Log
6. Link the call to the appropriate ticket using "Link Call Log to this Ticket"

### Linking Calls to Tickets

For calls that came in directly (not initiated from Helpdesk):

1. Open the HD Ticket you want to link the call to
2. Click the **three-dot menu → JustCall → "Link Call Log to this Ticket"**
3. A modal will show all unlinked call logs with:
   - From/To numbers
   - Call type and status
   - Duration
   - **Play button** for recordings (if available)
4. Select one or more calls using checkboxes (or use "Select All")
5. Click **"Link to this ticket"** button
6. Selected calls are now linked to the ticket

## How It Works

### Outgoing Calls (Auto-Linked)

```
User clicks "Call via JustCall"
        ↓
Opens: https://app.justcall.io/dialer?numbers=...&metadata={"ticket_id":"123"}
        ↓
User makes call in JustCall
        ↓
JustCall sends webhook with metadata
        ↓
Call logged to TP Call Log + Auto-linked to ticket
```

### Incoming Calls (Manual Link)

```
Call comes in to JustCall number
        ↓
JustCall sends webhook (no metadata)
        ↓
Call logged to TP Call Log (unlinked)
        ↓
User manually links via "Link Call Log to this Ticket"
```

## Data Mapping

### JustCall → TP Call Log

| TP Call Log | JustCall Source | Notes |
|-------------|-----------------|-------|
| `id` | `data.call_sid` | JustCall unique identifier |
| `from` | `data.justcall_number` (outgoing) / `data.contact_number` (incoming) | Caller number |
| `to` | `data.contact_number` (outgoing) / `data.justcall_number` (incoming) | Receiver number |
| `type` | `data.call_info.direction` | "Incoming" or "Outgoing" |
| `status` | `data.call_info.type` | Mapped to TP Call Log statuses |
| `duration` | `data.call_duration.total_duration` | In seconds |
| `medium` | Hardcoded | "JustCall" |
| `start_time` | `data.call_date` + `data.call_time` | Combined datetime |
| `end_time` | Calculated | start_time + duration |
| `receiver`/`caller` | `data.agent_email` | Only if user exists in Frappe |
| `recording_url` | `data.call_info.recording` | Full recording URL |

### Status Mapping

| JustCall | TP Call Log |
|----------|-------------|
| answered | Completed |
| unanswered | No Answer |
| missed | No Answer |
| voicemail | No Answer |
| failed | Failed |
| busy | Busy |
| completed | Completed |
| canceled | Canceled |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/method/justcall_integration.api.handle_call_webhook` | POST | JustCall webhook handler |
| `/api/method/justcall_integration.api.get_calls_without_ticket` | GET | Get unattached call logs |
| `/api/method/justcall_integration.api.link_calls_to_ticket` | POST | Link calls to ticket |
| `/api/method/justcall_integration.api.get_ticket_contact_phone` | GET | Get contact phone for dialer |

## Troubleshooting

### Calls not appearing in TP Call Log

1. Check that the webhook URL is correctly configured in JustCall
2. Verify the webhook is subscribed to `call.completed` event
3. Check Error Log in Frappe for any webhook errors
4. Ensure the site is publicly accessible

### "Call via JustCall" button not showing

1. Verify the HD Form Script "JustCall Integration" is enabled
2. Check that you're viewing an HD Ticket (not other doctype)
3. Ensure the user has appropriate permissions

### Linking not working

1. Ensure the call is not already linked to the ticket
2. Check Error Log for any API errors
3. Verify the call exists in TP Call Log

## Security

- Webhook endpoint accepts POST requests only
- No API secrets or credentials stored in the app
- Error logging prevents sensitive data exposure

## License

MIT License - see [license.txt](license.txt) for details.

---

Built with ❤️ by Mastiff Systems
