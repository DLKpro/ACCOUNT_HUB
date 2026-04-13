import typer

from account_hub.cli.auth_commands import auth_app
from account_hub.cli.email_commands import email_app

app = typer.Typer(
    name="accounthub",
    help="Account Hub — identity aggregation CLI",
    no_args_is_help=True,
)

app.add_typer(auth_app, name="auth", help="Register, login, and manage your account")
app.add_typer(email_app, name="email", help="Link, list, and unlink email addresses")


@app.command()
def server():
    """Start the Account Hub API server."""
    import uvicorn

    from account_hub.config import settings

    uvicorn.run(
        "account_hub.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )


if __name__ == "__main__":
    app()
