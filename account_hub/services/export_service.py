from __future__ import annotations

import csv
import io

from account_hub.db.models import DiscoveredAccount


def export_to_csv(accounts: list[DiscoveredAccount]) -> str:
    """Generate CSV string from discovered accounts."""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "email_address",
        "service_name",
        "service_domain",
        "source",
        "confidence",
        "breach_date",
        "discovered_at",
    ])

    for a in accounts:
        writer.writerow([
            a.email_address,
            a.service_name,
            a.service_domain or "",
            a.source,
            a.confidence,
            str(a.breach_date) if a.breach_date else "",
            a.discovered_at.isoformat() if a.discovered_at else "",
        ])

    return output.getvalue()
