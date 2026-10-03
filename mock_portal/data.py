"""
Mock data for the IT Portal.

Contains simulated service statuses, tickets, and team info.
The VPN is intentionally set to 'down' and CRM to 'degraded'
to give the agent something to discover and act on.
"""

from datetime import datetime, timedelta
import random

# Service statuses — VPN is DOWN, CRM is DEGRADED (for the demo)
SERVICES = [
    {
        "id": 1,
        "name": "Email Server",
        "status": "operational",
        "uptime": "99.9%",
        "last_checked": datetime.now().isoformat(),
        "description": "Corporate email service (Exchange)",
        "response_time_ms": 45,
    },
    {
        "id": 2,
        "name": "VPN Gateway",
        "status": "down",
        "uptime": "94.2%",
        "last_checked": datetime.now().isoformat(),
        "last_incident": (datetime.now() - timedelta(hours=2)).isoformat(),
        "description": "Remote access VPN for employees",
        "response_time_ms": None,
        "error_message": "Connection timeout - primary gateway unreachable",
    },
    {
        "id": 3,
        "name": "CRM System",
        "status": "degraded",
        "uptime": "97.5%",
        "last_checked": datetime.now().isoformat(),
        "description": "Customer Relationship Management (Salesforce)",
        "response_time_ms": 5200,
        "error_message": "Elevated response times detected",
    },
    {
        "id": 4,
        "name": "Database Cluster",
        "status": "operational",
        "uptime": "99.99%",
        "last_checked": datetime.now().isoformat(),
        "description": "Primary PostgreSQL cluster",
        "response_time_ms": 12,
    },
    {
        "id": 5,
        "name": "File Storage",
        "status": "operational",
        "uptime": "99.8%",
        "last_checked": datetime.now().isoformat(),
        "description": "Network file storage (NAS)",
        "response_time_ms": 85,
    },
    {
        "id": 6,
        "name": "CI/CD Pipeline",
        "status": "operational",
        "uptime": "99.5%",
        "last_checked": datetime.now().isoformat(),
        "description": "Jenkins build and deployment system",
        "response_time_ms": 200,
    },
]

# Existing tickets
TICKETS = [
    {
        "id": "TKT-001",
        "title": "Slow login on accounting portal",
        "description": "Users report 10+ second login times on the accounting portal since yesterday.",
        "status": "open",
        "priority": "P2",
        "created_at": (datetime.now() - timedelta(days=1)).isoformat(),
        "assigned_to": "Priya Sharma",
        "service": "Database Cluster",
    },
    {
        "id": "TKT-002",
        "title": "Email delivery delays",
        "description": "Some external emails are delayed by 15-30 minutes.",
        "status": "in_progress",
        "priority": "P3",
        "created_at": (datetime.now() - timedelta(days=2)).isoformat(),
        "assigned_to": "Mike Johnson",
        "service": "Email Server",
    },
]

# Auto-incrementing ticket counter
_next_ticket_num = 3


def get_next_ticket_id():
    """Generate the next ticket ID."""
    global _next_ticket_num
    ticket_id = f"TKT-{_next_ticket_num:03d}"
    _next_ticket_num += 1
    return ticket_id


def get_services():
    """Get all services with current status."""
    return SERVICES


def get_service(service_id: int):
    """Get a specific service by ID."""
    for service in SERVICES:
        if service["id"] == service_id:
            return service
    return None


def get_tickets():
    """Get all tickets."""
    return TICKETS


def get_ticket(ticket_id: str):
    """Get a specific ticket by ID."""
    for ticket in TICKETS:
        if ticket["id"] == ticket_id:
            return ticket
    return None


def create_ticket(title: str, description: str, priority: str, service: str, assigned_to: str = "Unassigned"):
    """Create a new ticket."""
    ticket = {
        "id": get_next_ticket_id(),
        "title": title,
        "description": description,
        "status": "open",
        "priority": priority,
        "created_at": datetime.now().isoformat(),
        "assigned_to": assigned_to,
        "service": service,
    }
    TICKETS.append(ticket)
    return ticket
