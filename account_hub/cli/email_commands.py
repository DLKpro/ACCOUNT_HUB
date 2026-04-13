from __future__ import annotations

import http.server
import threading
import time
import webbrowser
from typing import Optional
from urllib.parse import parse_qs, urlparse

import typer
from rich.console import Console
from rich.table import Table

from account_hub.cli.helpers import get_client

email_app = typer.Typer(no_args_is_help=True)
console = Console()


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    """Tiny HTTP handler that catches the OAuth redirect callback."""

    code: Optional[str] = None
    state: Optional[str] = None
    received = threading.Event()

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        _CallbackHandler.code = params.get("code", [None])[0]
        _CallbackHandler.state = params.get("state", [None])[0]

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(
            b"<html><body><h2>Authorization complete.</h2>"
            b"<p>You can close this tab and return to the terminal.</p>"
            b"</body></html>"
        )
        _CallbackHandler.received.set()

    def log_message(self, format, *args):
        pass  # Suppress noisy logs


def _find_free_port() -> int:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@email_app.command("link")
def link_email(
    provider: str = typer.Argument(..., help="OAuth provider: google, microsoft, apple, meta"),
):
    """Link an email address via OAuth."""
    provider = provider.lower().strip()

    with get_client() as client:
        if provider == "microsoft":
            _device_code_flow(client, provider)
        else:
            _loopback_flow(client, provider)


def _loopback_flow(client, provider: str) -> None:
    """Handle OAuth via local HTTP callback server."""
    port = _find_free_port()

    # Reset handler state
    _CallbackHandler.code = None
    _CallbackHandler.state = None
    _CallbackHandler.received.clear()

    # Start local server
    server = http.server.HTTPServer(("127.0.0.1", port), _CallbackHandler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()

    # Initiate OAuth
    resp = client.post("/oauth/initiate", json={"provider": provider, "redirect_port": port})
    if resp.status_code != 200:
        console.print(f"[red]Failed to start OAuth: {resp.json().get('detail', resp.text)}[/red]")
        server.server_close()
        raise typer.Exit(1)

    data = resp.json()
    auth_url = data["auth_url"]

    console.print(f"Opening browser for {provider} authentication...")
    webbrowser.open(auth_url)
    console.print("[dim]Waiting for authorization (timeout: 120s)...[/dim]")

    # Wait for callback
    if not _CallbackHandler.received.wait(timeout=120):
        console.print("[red]Timed out waiting for authorization.[/red]")
        server.server_close()
        raise typer.Exit(1)

    server.server_close()

    if not _CallbackHandler.code:
        console.print("[red]No authorization code received.[/red]")
        raise typer.Exit(1)

    # Exchange code
    resp = client.post("/oauth/callback", json={
        "provider": provider,
        "code": _CallbackHandler.code,
        "state": _CallbackHandler.state,
    })

    if resp.status_code == 200:
        result = resp.json()
        console.print(
            f"[green]Linked {result['email_address']} ({provider}) successfully.[/green]"
        )
    elif resp.status_code == 409:
        console.print(f"[yellow]{resp.json().get('detail', 'Email already linked')}[/yellow]")
    else:
        console.print(f"[red]Error: {resp.status_code} — {resp.json().get('detail', resp.text)}[/red]")
        raise typer.Exit(1)


def _device_code_flow(client, provider: str) -> None:
    """Handle OAuth via device code flow (Microsoft)."""
    resp = client.post("/oauth/initiate", json={"provider": provider})
    if resp.status_code != 200:
        console.print(f"[red]Failed to start OAuth: {resp.json().get('detail', resp.text)}[/red]")
        raise typer.Exit(1)

    data = resp.json()
    user_code = data.get("user_code")
    verification_uri = data.get("verification_uri")
    device_code = data.get("device_code")
    interval = data.get("interval", 5)

    console.print(f"\nGo to [bold]{verification_uri}[/bold]")
    console.print(f"Enter code: [bold green]{user_code}[/bold green]\n")

    # Poll until authorized or timeout
    for _ in range(120 // interval):
        time.sleep(interval)
        resp = client.post("/oauth/poll", json={
            "provider": provider,
            "device_code": device_code,
        })

        if resp.status_code == 200:
            result = resp.json()
            if result.get("status") == "pending":
                continue
            console.print(
                f"[green]Linked {result['email_address']} ({provider}) successfully.[/green]"
            )
            return
        elif resp.status_code == 409:
            console.print(f"[yellow]{resp.json().get('detail', 'Email already linked')}[/yellow]")
            return
        else:
            console.print(f"[red]Error: {resp.status_code} — {resp.text}[/red]")
            raise typer.Exit(1)

    console.print("[red]Timed out waiting for authorization.[/red]")
    raise typer.Exit(1)


@email_app.command("list")
def list_emails():
    """List all linked email addresses."""
    with get_client() as client:
        resp = client.get("/emails")

    if resp.status_code != 200:
        console.print(f"[red]Error: {resp.status_code} — {resp.text}[/red]")
        raise typer.Exit(1)

    emails = resp.json()
    if not emails:
        console.print("[dim]No linked emails. Run: accounthub email link <provider>[/dim]")
        return

    table = Table(title="Linked Emails")
    table.add_column("Email", style="cyan")
    table.add_column("Provider", style="green")
    table.add_column("Verified", style="yellow")
    table.add_column("Linked At")
    table.add_column("ID", style="dim")

    for e in emails:
        table.add_row(
            e["email_address"],
            e["provider"],
            "Yes" if e["is_verified"] else "No",
            e["linked_at"],
            e["id"],
        )

    console.print(table)


@email_app.command("unlink")
def unlink_email(
    email_id: str = typer.Argument(..., help="ID of the linked email to remove"),
):
    """Unlink an email address."""
    with get_client() as client:
        resp = client.delete(f"/emails/{email_id}")

    if resp.status_code == 204:
        console.print("[green]Email unlinked successfully.[/green]")
    elif resp.status_code == 404:
        console.print("[red]Linked email not found.[/red]")
        raise typer.Exit(1)
    else:
        console.print(f"[red]Error: {resp.status_code} — {resp.text}[/red]")
        raise typer.Exit(1)
