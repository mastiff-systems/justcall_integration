# AGENTS.md - JustCall Integration

## Overview

Frappe app that integrates JustCall.io with Frappe Helpdesk for click-to-call functionality and call logging.

## Architecture

### Files Structure

```
justcall_integration/
├── justcall_integration/
│   ├── __init__.py
│   ├── api.py              # Webhook handlers and API methods
│   └── hooks.py            # App config, fixtures
├── fixtures/
│   ├── custom_field.json   # HD Ticket.via_justcall Check field
│   ├── hd_form_script.json # JustCall buttons on ticket form
│   └── property_setter.json # TP Call Log recording_url → Long Text
├── README.md
├── AGENTS.md               # This file
└── license.txt
```

### Dependencies

- `helpdesk`: Required for HD Ticket integration
- `telephony`: Required for TP Call Log and `link_call_with_doc()` util

### Fixtures

All fixtures are included in the app and loaded on install:

1. **Custom Field** (`HD Ticket.via_justcall`): Check field to mark tickets created via JustCall
2. **HD Form Script** (JustCall Integration): Three buttons on ticket form:
   - "Call via JustCall" - Opens dialer with contact pre-filled
   - "Standby via JustCall" - Opens blank dialer for incoming
   - "Link Call Log to this Ticket" - Modal to link unattached calls
3. **Property Setter** (`TP Call Log.recording_url`): Changes fieldtype from Data to Long Text

## API Reference

### Webhook Handler

**Endpoint:** `/api/method/justcall_integration.api.handle_call_webhook`

**Event Supported:** `call.completed`

**Payload Processing:**
- `data.call_sid` → `id` (TP Call Log)
- `data.call_info.direction` → `type` ("Incoming"/"Outgoing")
- `data.call_info.type` → `status` (mapped via `map_call_status()`)
- `data.contact_number` / `data.justcall_number` → `from`/`to` (swapped based on direction)
- `data.agent_email` → `receiver`/`caller` (only if user exists)
- `metadata.ticket_id` → Auto-link to HD Ticket via `link_call_with_doc()`

### API Methods

**`get_calls_without_ticket()`**
- Returns TP Call Logs not linked to any HD Ticket
- Used by linking modal

**`link_calls_to_ticket(ticket_id, call_log_names)`**
- Links multiple TP Call Logs to a single HD Ticket
- Accepts array of TP Call Log names
- Uses `link_call_with_doc()` for each

**`get_ticket_contact_phone(ticket_id)`**
- Returns contact phone for pre-filling JustCall dialer

## Frontend (HD Form Script)

The JavaScript in `fixtures/hd_form_script.json` provides three buttons:

### Button 1: Call via JustCall
```javascript
// Opens dialer with metadata for auto-linking
const ticketId = frm.doc.name;
const phone = frm._justcall_phone;
const metadata = { ticket_id: ticketId, subject: frm.doc.subject };
const url = `https://app.justcall.io/dialer?numbers=${phone}&metadata=${JSON.stringify(metadata)}`;
window.open(url, '_blank');
```

### Button 2: Standby via JustCall
```javascript
// Opens blank dialer, no metadata
window.open('https://app.justcall.io/dialer', '_blank');
```

### Button 3: Link Call Log to this Ticket
```javascript
// Opens custom modal (pure JS, no frappe.ui.Dialog to avoid $dialog issues)
// 1. Fetch unattached calls from `get_calls_without_ticket`
// 2. Render checkboxes per call row
// 3. "Link to this ticket" calls `link_calls_to_ticket` API
// 4. Refreshes page on success
```

**Important:** The modal uses pure JavaScript DOM manipulation (not `frappe.ui.Dialog`) because the Helpdesk SPA context doesn't provide `$dialog` in the same way.

## Key Behaviors

### Auto-Linking

Outgoing calls from Helpdesk include `ticket_id` in metadata. When webhook fires:
1. Extract `metadata.ticket_id`
2. Verify `HD Ticket` exists
3. Call `link_call_with_doc(call_log, "HD Ticket", ticket_id)`

### Manual Linking

Incoming calls have no metadata in webhook. They are logged but remain unlinked. Users manually link via modal.

### Duration Formatting

- Stored as integer seconds in `TP Call Log.duration`
- Formatted as "Xm Ys" for UI display in linking modal

## Status Mapping

See `map_call_status()` in `api.py`:

```python
{
    "answered": "Completed",
    "unanswered": "No Answer",
    "missed": "No Answer",
    "voicemail": "No Answer",
    "failed": "Failed",
    "busy": "Busy",
    "completed": "Completed",
    "canceled": "Canceled"
}
```

## Common Issues

### $dialog undefined
**Solution:** Use pure JS modal instead of `frappe.ui.Dialog`

### Recording URL too long
**Solution:** Property Setter changes `recording_url` to Long Text fieldtype

### Call not auto-linking
**Check:** Metadata was passed correctly in dialer URL, webhook payload includes metadata

## Development Notes

- No settings Doctype (no API secrets)
- Webhook is open endpoint (allow_guest=True)
- Fixtures must be re-exported if changed:
  ```bash
  bench --site your-site export-fixtures --app justcall_integration
  ```
