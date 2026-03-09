# Copyright (c) 2026, Mastiff Systems and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from telephony.utils import link_call_with_contact, link_call_with_doc


@frappe.whitelist(allow_guest=True)
def handle_call_webhook():
	"""
	Handle JustCall webhooks for call events.
	Logs all calls to TP Call Log. Links to HD Ticket only if metadata contains ticket_id.

	Webhook URL: /api/method/justcall_integration.api.handle_call_webhook
	"""
	if frappe.request.method != "POST":
		frappe.throw(_("Only POST requests are allowed"), frappe.PermissionError)

	payload = frappe.request.get_json() or {}

	try:
		event_type = payload.get("type", "")

		if event_type == "call.completed":
			handle_call_completed(payload)

	except Exception as e:
		frappe.log_error(message=f"JustCall Webhook Error: {e!s}", title="JustCall Webhook Error")
		frappe.db.rollback()

	return {"status": "success"}


def handle_call_completed(payload):
	"""
	Handle call.completed webhook from JustCall.
	Creates or updates TP Call Log. Links to HD Ticket only if metadata has ticket_id.
	"""
	data = payload.get("data", {})
	metadata = payload.get("metadata", {}) or {}

	# Extract call ID from JustCall (use call_sid as id)
	call_id = data.get("call_sid", "")
	if not call_id:
		return

	# Check if call log already exists
	existing_call_log = frappe.db.exists("TP Call Log", call_id)

	# Get or create call log
	if existing_call_log:
		call_log = frappe.get_doc("TP Call Log", call_id)
	else:
		call_log = frappe.new_doc("TP Call Log")
		call_log.id = call_id

	# Get call direction
	call_info = data.get("call_info", {})
	direction = call_info.get("direction", "Outgoing")
	is_incoming = direction == "Incoming"

	# Map fields
	call_log.medium = "JustCall"
	call_log.type = "Incoming" if is_incoming else "Outgoing"
	call_log.status = map_call_status(call_info.get("type", ""))
	call_log.duration = get_call_duration(data)

	# Phone numbers based on direction
	contact_number = data.get("contact_number", "")
	justcall_number = data.get("justcall_number", "")

	if is_incoming:
		# Incoming: from = caller (contact), to = JustCall number
		setattr(call_log, "from", contact_number)
		call_log.to = justcall_number
		call_log.receiver = get_agent_email(data)
	else:
		# Outgoing: from = JustCall number, to = contact
		setattr(call_log, "from", justcall_number)
		call_log.to = contact_number
		call_log.caller = get_agent_email(data)

	# Times
	call_log.start_time = get_start_time(data)
	call_log.end_time = get_end_time(data)

	# Recording URL
	call_log.recording_url = call_info.get("recording", "")

	# Link with contact
	if contact_number:
		link_call_with_contact(contact_number, call_log)

	# Link with HD Ticket ONLY if metadata contains ticket_id
	ticket_id = metadata.get("ticket_id")
	if ticket_id:
		ticket_id_str = str(ticket_id)
		if frappe.db.exists("HD Ticket", ticket_id_str):
			link_call_with_doc(call_log, "HD Ticket", ticket_id_str)

	call_log.save(ignore_permissions=True)
	frappe.db.commit()

	return call_log


def map_call_status(justcall_type):
	"""
	Map JustCall call_info.type to TP Call Log status.
	"""
	status_map = {
		"answered": "Completed",
		"unanswered": "No Answer",
		"missed": "No Answer",
		"voicemail": "No Answer",
		"failed": "Failed",
		"busy": "Busy",
		"completed": "Completed",
		"canceled": "Canceled",
		"cancelled": "Canceled",
		"ringing": "Ringing",
		"in-progress": "In Progress",
		"inprogress": "In Progress",
		"queued": "Queued",
		"initiated": "Initiated",
	}

	return status_map.get(justcall_type.lower(), "Completed")


def get_call_duration(data):
	"""
	Extract duration in seconds from JustCall payload.
	Frappe Duration field expects seconds as integer.
	"""
	duration_data = data.get("call_duration", {})
	total_duration = duration_data.get("total_duration", 0)

	if total_duration:
		try:
			return int(float(total_duration))
		except (ValueError, TypeError):
			pass

	return 0


def get_start_time(data):
	"""Extract start time from JustCall payload."""
	call_date = data.get("call_date", "")
	call_time = data.get("call_time", "")

	if call_date and call_time:
		datetime_str = f"{call_date} {call_time}"
		try:
			from datetime import datetime

			dt = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
			return dt.strftime("%Y-%m-%d %H:%M:%S")
		except Exception:
			pass

	return None


def get_end_time(data):
	"""Calculate end time from start_time + duration."""
	start_time = get_start_time(data)
	duration = get_call_duration(data)

	if start_time and duration:
		from datetime import datetime, timedelta

		try:
			dt = datetime.strptime(str(start_time), "%Y-%m-%d %H:%M:%S")
			end_dt = dt + timedelta(seconds=int(duration))
			return end_dt.strftime("%Y-%m-%d %H:%M:%S")
		except Exception:
			pass

	return None


def get_agent_email(data):
	"""Extract agent email from JustCall payload."""
	agent_email = data.get("agent_email", "")

	if agent_email and frappe.db.exists("User", agent_email):
		return agent_email

	return None


def format_duration(seconds):
	"""Format duration in seconds to readable string."""
	if not seconds:
		return "0s"

	minutes = int(seconds // 60)
	remaining_seconds = int(seconds % 60)

	if minutes > 0:
		return f"{minutes}m {remaining_seconds}s"
	return f"{remaining_seconds}s"


@frappe.whitelist()
def get_calls_without_ticket():
	"""
	Get all TP Call Log records that are NOT linked to any HD Ticket.
	Used by the "Link Call Log to this Ticket" feature.
	"""
	all_calls = frappe.get_all(
		"TP Call Log",
		fields=[
			"name",
			"id",
			"from",
			"to",
			"type",
			"status",
			"duration",
			"start_time",
			"creation",
			"medium",
			"recording_url",
		],
		order_by="creation desc",
		limit=100,
	)

	calls_without_ticket = []

	for call in all_calls:
		has_ticket_link = frappe.db.exists(
			"Dynamic Link", {"parenttype": "TP Call Log", "parent": call.name, "link_doctype": "HD Ticket"}
		)

		if not has_ticket_link:
			call.duration_formatted = format_duration(call.duration)
			calls_without_ticket.append(call)

	return calls_without_ticket


@frappe.whitelist()
def link_calls_to_ticket(ticket_id, call_log_names):
	"""
	Link multiple TP Call Logs to an HD Ticket.
	"""
	if not frappe.db.exists("HD Ticket", ticket_id):
		frappe.throw(_("HD Ticket not found"))

	if isinstance(call_log_names, str):
		call_log_names = json.loads(call_log_names)

	if not call_log_names or not isinstance(call_log_names, list):
		return {"success": False, "message": "No calls selected"}

	linked_count = 0
	errors = []

	for call_name in call_log_names:
		try:
			if not frappe.db.exists("TP Call Log", call_name):
				errors.append(f"Call Log {call_name} not found")
				continue

			call_log = frappe.get_doc("TP Call Log", call_name)

			if call_log.has_link("HD Ticket", ticket_id):
				continue

			link_call_with_doc(call_log, "HD Ticket", ticket_id)
			call_log.save(ignore_permissions=True)
			linked_count += 1

		except Exception as e:
			errors.append(f"Failed to link {call_name}: {e!s}")

	frappe.db.commit()

	return {"success": True, "linked_count": linked_count, "errors": errors}


@frappe.whitelist()
def get_ticket_contact_phone(ticket_id):
	"""
	Get the primary phone number for a ticket's contact.
	Used by the HD Form Script to populate the dialer.
	"""
	if not ticket_id:
		return {"phone": None}

	ticket = frappe.get_doc("HD Ticket", ticket_id)

	if not ticket.contact:
		return {"phone": None}

	contact = frappe.get_doc("Contact", ticket.contact)

	phone = contact.phone or contact.mobile_no

	return {
		"phone": phone,
		"contact_name": contact.full_name or contact.first_name,
	}
