import typer
from rich.console import Console

from account_hub.cli.helpers import (
    clear_credentials,
    get_anon_client,
    get_client,
    save_credentials,
)

auth_app = typer.Typer(no_args_is_help=True)
console = Console()


@auth_app.command()
def register(
    username: str = typer.Option(..., prompt=True, help="Your Account Hub username"),
    password: str = typer.Option(
        ..., prompt=True, confirmation_prompt=True, hide_input=True, help="Your password"
    ),
):
    """Create a new Account Hub account."""
    with get_anon_client() as client:
        resp = client.post("/auth/register", json={"username": username, "password": password})

    if resp.status_code == 201:
        data = resp.json()
        save_credentials(data["access_token"], data["refresh_token"])
        console.print(f"[green]Account created. Logged in as {data['username']}.[/green]")
    elif resp.status_code == 409:
        console.print(f"[red]Username '{username}' is already taken.[/red]")
        raise typer.Exit(1)
    elif resp.status_code == 400:
        console.print(f"[red]{resp.json().get('detail', 'Invalid input')}[/red]")
        raise typer.Exit(1)
    else:
        console.print(f"[red]Error: {resp.status_code} — {resp.text}[/red]")
        raise typer.Exit(1)


@auth_app.command()
def login(
    username: str = typer.Option(..., prompt=True, help="Your Account Hub username"),
    password: str = typer.Option(..., prompt=True, hide_input=True, help="Your password"),
):
    """Log in to your Account Hub account."""
    with get_anon_client() as client:
        resp = client.post("/auth/login", json={"username": username, "password": password})

    if resp.status_code == 200:
        data = resp.json()
        save_credentials(data["access_token"], data["refresh_token"])
        console.print(f"[green]Logged in as {username}.[/green]")
    elif resp.status_code == 401:
        console.print("[red]Invalid username or password.[/red]")
        raise typer.Exit(1)
    else:
        console.print(f"[red]Error: {resp.status_code} — {resp.text}[/red]")
        raise typer.Exit(1)


@auth_app.command()
def me():
    """Show your Account Hub profile."""
    with get_client() as client:
        resp = client.get("/auth/me")

    if resp.status_code == 200:
        data = resp.json()
        console.print(f"[bold]Username:[/bold] {data['username']}")
        console.print(f"[bold]User ID:[/bold]  {data['id']}")
        console.print(f"[bold]Active:[/bold]   {data['is_active']}")
        console.print(f"[bold]Created:[/bold]  {data['created_at']}")
    elif resp.status_code == 401:
        console.print("[red]Session expired. Run: accounthub auth login[/red]")
        raise typer.Exit(1)
    else:
        console.print(f"[red]Error: {resp.status_code} — {resp.text}[/red]")
        raise typer.Exit(1)


@auth_app.command()
def logout():
    """Log out by clearing saved credentials."""
    clear_credentials()
    console.print("[green]Logged out.[/green]")
