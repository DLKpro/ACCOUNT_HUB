import webbrowser

import typer
from rich.console import Console
from rich.table import Table

from account_hub.cli.helpers import clear_credentials, get_client, handle_api_error

close_app = typer.Typer(no_args_is_help=True)
console = Console()


@close_app.command("list")
def list_closure_requests():
    """List all account closure requests."""
    with get_client() as client:
        resp = client.get("/accounts/close-requests")

    if resp.status_code != 200:
        handle_api_error(resp, console)

    requests = resp.json()
    if not requests:
        console.print("[dim]No closure requests. Run: accounthub close request <account-id>[/dim]")
        return

    table = Table(title="Closure Requests")
    table.add_column("Service", style="cyan")
    table.add_column("Method", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("URL")
    table.add_column("ID", style="dim")

    for r in requests:
        table.add_row(
            r["service_name"],
            r["method"],
            r["status"],
            r.get("deletion_url", "") or "",
            r["id"][:8] + "...",
        )

    console.print(table)


@close_app.command("request")
def request_closure(
    account_id: str = typer.Argument(..., help="ID of the discovered account to close"),
):
    """Request closure of a discovered third-party account."""
    with get_client() as client:
        resp = client.post("/accounts/close", json={"discovered_account_id": account_id})

    if resp.status_code == 201:
        data = resp.json()
        console.print(f"[green]Closure requested for {data['service_name']}[/green]")
        console.print(f"  Method: {data['method']}")
        if data.get("deletion_url"):
            console.print(f"  URL: {data['deletion_url']}")
        if data.get("notes"):
            console.print(f"  Notes: {data['notes']}")

        if data.get("deletion_url") and data["method"] == "web":
            open_browser = typer.confirm("Open deletion page in browser?", default=True)
            if open_browser:
                webbrowser.open(data["deletion_url"])
    elif resp.status_code == 404:
        console.print("[red]Discovered account not found.[/red]")
        raise typer.Exit(1)
    else:
        handle_api_error(resp, console)


@close_app.command("complete")
def mark_complete(
    request_id: str = typer.Argument(..., help="ID of the closure request to mark complete"),
):
    """Mark a closure request as completed."""
    with get_client() as client:
        resp = client.post("/accounts/close/complete", json={"request_id": request_id})

    if resp.status_code == 200:
        data = resp.json()
        console.print(f"[green]{data['service_name']} marked as closed.[/green]")
    elif resp.status_code == 404:
        console.print("[red]Closure request not found.[/red]")
        raise typer.Exit(1)
    else:
        handle_api_error(resp, console)


@close_app.command("info")
def closure_info(
    service_name: str = typer.Argument(..., help="Name of the service to look up"),
):
    """Look up deletion instructions for a service."""
    with get_client() as client:
        resp = client.get(f"/accounts/close-info/{service_name}")

    if resp.status_code != 200:
        handle_api_error(resp, console)

    data = resp.json()
    console.print(f"[bold]{data['service_name']}[/bold]")
    console.print(f"  Difficulty: {data['difficulty']}")
    console.print(f"  Method:     {data['method']}")
    if data.get("deletion_url"):
        console.print(f"  URL:        {data['deletion_url']}")
    if data.get("notes"):
        console.print(f"  Notes:      {data['notes']}")


@close_app.command("delete-account")
def delete_account(
    password: str = typer.Option(..., prompt=True, hide_input=True, help="Confirm your password"),
):
    """Permanently delete your Account Hub account and all data."""
    confirm = typer.confirm(
        "This will permanently delete your account, all linked emails, "
        "scan history, and closure requests. Continue?",
        default=False,
    )
    if not confirm:
        console.print("[dim]Cancelled.[/dim]")
        raise typer.Exit(0)

    with get_client() as client:
        resp = client.request("DELETE", "/auth/account", json={"password": password})

    if resp.status_code == 204:
        clear_credentials()
        console.print("[green]Account deleted. All data has been purged.[/green]")
    elif resp.status_code == 403:
        console.print("[red]Incorrect password.[/red]")
        raise typer.Exit(1)
    else:
        handle_api_error(resp, console)
