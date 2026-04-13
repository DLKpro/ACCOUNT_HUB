from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from account_hub.cli.helpers import get_client, handle_api_error

search_app = typer.Typer(no_args_is_help=True)
console = Console()


@search_app.command("run")
def run_search():
    """Run an account discovery scan across all linked emails."""
    with get_client() as client:
        resp = client.post("/search")

    if resp.status_code != 201:
        handle_api_error(resp, console)

    data = resp.json()
    session_id = data["scan_session_id"]
    status = data["status"]

    if status == "completed":
        _show_scan_results(session_id)
    else:
        console.print(f"[yellow]Scan {session_id} is {status}.[/yellow]")


@search_app.command("results")
def show_results(
    session_id: str = typer.Argument(
        None, help="Scan session ID. Defaults to most recent scan."
    ),
):
    """Show results from a scan session."""
    if session_id is None:
        session_id = _get_latest_session_id()
        if session_id is None:
            console.print("[dim]No scans found. Run: accounthub search run[/dim]")
            raise typer.Exit(1)

    _show_scan_results(session_id)


@search_app.command("history")
def scan_history(
    limit: int = typer.Option(10, help="Number of scans to show"),
):
    """List past scan sessions."""
    with get_client() as client:
        resp = client.get("/search/history", params={"limit": limit})

    if resp.status_code != 200:
        handle_api_error(resp, console)

    scans = resp.json()
    if not scans:
        console.print("[dim]No scans found. Run: accounthub search run[/dim]")
        return

    table = Table(title="Scan History")
    table.add_column("ID", style="dim")
    table.add_column("Status", style="green")
    table.add_column("Emails", justify="right")
    table.add_column("Accounts Found", justify="right", style="cyan")
    table.add_column("Date")

    for s in scans:
        table.add_row(
            s["id"][:8] + "...",
            s["status"],
            str(s["emails_scanned"]),
            str(s["accounts_found"]),
            s.get("created_at", ""),
        )

    console.print(table)


@search_app.command("export")
def export_results(
    session_id: str = typer.Argument(
        None, help="Scan session ID. Defaults to most recent scan."
    ),
    output: str = typer.Option("results.csv", "--output", "-o", help="Output file path"),
):
    """Export scan results to CSV."""
    if session_id is None:
        session_id = _get_latest_session_id()
        if session_id is None:
            console.print("[dim]No scans found. Run: accounthub search run[/dim]")
            raise typer.Exit(1)

    with get_client() as client:
        resp = client.get(f"/search/{session_id}/export")

    if resp.status_code != 200:
        handle_api_error(resp, console)

    Path(output).write_text(resp.text)
    console.print(f"[green]Exported to {output}[/green]")


def _get_latest_session_id() -> str | None:
    """Fetch the most recent scan session ID."""
    with get_client() as client:
        resp = client.get("/search/history", params={"limit": 1})

    if resp.status_code != 200 or not resp.json():
        return None
    return resp.json()[0]["id"]


def _show_scan_results(session_id: str) -> None:
    """Fetch and display scan results in a Rich table."""
    with get_client() as client:
        resp = client.get(f"/search/{session_id}")

    if resp.status_code != 200:
        handle_api_error(resp, console)

    data = resp.json()
    results = data.get("results", [])

    console.print(
        f"\n[bold]Scan:[/bold] {data['id'][:8]}... | "
        f"[bold]Status:[/bold] {data['status']} | "
        f"[bold]Emails scanned:[/bold] {data['emails_scanned']} | "
        f"[bold]Accounts found:[/bold] {data['accounts_found']}\n"
    )

    if not results:
        console.print("[dim]No accounts discovered.[/dim]")
        return

    table = Table(title="Discovered Accounts")
    table.add_column("Email", style="cyan")
    table.add_column("Service", style="green")
    table.add_column("Domain")
    table.add_column("Source")
    table.add_column("Confidence", style="yellow")

    for r in results:
        table.add_row(
            r["email_address"],
            r["service_name"],
            r.get("service_domain", ""),
            r["source"],
            r["confidence"],
        )

    console.print(table)
