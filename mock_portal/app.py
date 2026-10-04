"""
Mock IT Portal - Flask application.

Simulates a company's internal IT portal with:
- Service status dashboard
- Support ticket system (list, create, view)
- REST API for programmatic access

The agent can interact with this via both browser automation and API calls.
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_cors import CORS
from mock_portal.data import get_services, get_service, get_tickets, get_ticket, create_ticket

app = Flask(__name__)
CORS(app)


# ──────────────────────────────────────
# WEB PAGES (for browser automation)
# ──────────────────────────────────────

@app.route("/")
def dashboard():
    """Service status dashboard."""
    services = get_services()
    # Count by status
    operational = sum(1 for s in services if s["status"] == "operational")
    degraded = sum(1 for s in services if s["status"] == "degraded")
    down = sum(1 for s in services if s["status"] == "down")

    return render_template(
        "dashboard.html",
        services=services,
        operational=operational,
        degraded=degraded,
        down=down,
        total=len(services),
    )


@app.route("/tickets")
def tickets_list():
    """Ticket listing page."""
    tickets = get_tickets()
    return render_template("tickets.html", tickets=tickets)


@app.route("/tickets/create", methods=["GET", "POST"])
def create_ticket_page():
    """Ticket creation form."""
    if request.method == "POST":
        title = request.form.get("title", "")
        description = request.form.get("description", "")
        priority = request.form.get("priority", "P3")
        service = request.form.get("service", "")
        assigned_to = request.form.get("assigned_to", "Unassigned")

        ticket = create_ticket(title, description, priority, service, assigned_to)
        return redirect(url_for("ticket_detail", ticket_id=ticket["id"]))

    services = get_services()
    return render_template("create_ticket.html", services=services)


@app.route("/tickets/<ticket_id>")
def ticket_detail(ticket_id):
    """Ticket detail page."""
    ticket = get_ticket(ticket_id)
    if not ticket:
        return "Ticket not found", 404
    return render_template("ticket_detail.html", ticket=ticket)


# ──────────────────────────────────────
# REST API (for API tool)
# ──────────────────────────────────────

@app.route("/api/services", methods=["GET"])
def api_services():
    """Get all services."""
    return jsonify({"services": get_services()})


@app.route("/api/services/<int:service_id>", methods=["GET"])
def api_service(service_id):
    """Get a specific service."""
    service = get_service(service_id)
    if service:
        return jsonify(service)
    return jsonify({"error": "Service not found"}), 404


@app.route("/api/tickets", methods=["GET"])
def api_tickets():
    """Get all tickets."""
    return jsonify({"tickets": get_tickets()})


@app.route("/api/tickets", methods=["POST"])
def api_create_ticket():
    """Create a new ticket via API."""
    data = request.json
    if not data:
        return jsonify({"error": "No JSON body provided"}), 400

    service_val = data.get("service")
    if not service_val and "service_id" in data:
        srv = get_service(data["service_id"])
        service_val = srv["name"] if srv else f"Service {data['service_id']}"

    if not service_val:
        return jsonify({"error": "Missing required field: service"}), 400

    required_fields = ["title", "description", "priority"]
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400

    ticket = create_ticket(
        title=data["title"],
        description=data["description"],
        priority=data["priority"],
        service=service_val,
        assigned_to=data.get("assigned_to", "Unassigned"),
    )
    return jsonify({"ticket": ticket, "message": "Ticket created successfully"}), 201


@app.route("/api/tickets/<ticket_id>", methods=["GET"])
def api_ticket(ticket_id):
    """Get a specific ticket."""
    ticket = get_ticket(ticket_id)
    if ticket:
        return jsonify(ticket)
    return jsonify({"error": "Ticket not found"}), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
