"""Scripts for bootstrapping the local development environment."""

# scripts/bootstrap.py
import shutil
from pathlib import Path


def bootstrap() -> None:
    """Bootstrap the local development environment.

    This function is meant to be run locally to ensure that all
    necessary files and directories are present for local development.
    """
    print("🚀 Initializing local development environment...")

    # 2 levels up from scripts/bootstrap.py gets us to the repository root
    root = Path(__file__).parent.parent
    env_example = root / ".github" / "workflows" / "secrets.env.example"
    env_actual = root / ".github" / "workflows" / "secrets.env"

    cache_dir = root / ".cache" / "act-artifacts"
    gitkeep_file = cache_dir / ".gitkeep"

    # 1. Handle secrets.env
    if env_actual.exists():
        print("✅ .github/workflows/secrets.env already exists.")
    else:
        if env_example.exists():
            shutil.copy(env_example, env_actual)
            print("🆕 Created .github/workflows/secrets.env from template.")
        else:
            # Fallback if someone forgot to commit the example
            env_actual.parent.mkdir(parents=True, exist_ok=True)
            env_actual.write_text("# GITHUB_TOKEN=your_real_github_token_here\n")
            print("🆕 Created a blank .github/workflows/secrets.env file.")

    print("\n📁 Checking local cache directories...")
    # 3. Handle .cache/act-artifacts/.gitkeep
    if gitkeep_file.exists():
        print("   ✅ .cache/act-artifacts/ is ready.")
    else:
        # mkdir(parents=True) will automatically create .cache/ and act-artifacts/ if missing
        cache_dir.mkdir(parents=True, exist_ok=True)
        gitkeep_file.write_text("# act artifact store — contents are gitignored\n")
        print("   🆕 Restored .cache/act-artifacts/ and .gitkeep file.")

    print("\n🎉 Local setup complete! You can now run your local 'act' workflows safely.")


if __name__ == "__main__":
    """Main entry point for the bootstrap script."""
    bootstrap()
