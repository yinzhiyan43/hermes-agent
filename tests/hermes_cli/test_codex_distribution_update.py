"""The installed fork must never select the upstream source as its update target."""
import subprocess


def test_update_check_follows_origin_even_with_upstream_remote(tmp_path, monkeypatch, capsys):
    from hermes_cli import main, update_cmd

    def git(root, *args):
        return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()

    source = tmp_path / "source"
    source.mkdir()
    git(source, "init", "-b", "main")
    git(source, "config", "user.name", "Test")
    git(source, "config", "user.email", "test@example.invalid")
    (source / "version").write_text("maintained fork")
    git(source, "add", "version")
    git(source, "commit", "-m", "distribution")
    installed = tmp_path / "installed"
    git(tmp_path, "clone", str(source), str(installed))
    # An upstream remote can exist for development; it must not be fetched by
    # client update checks. This intentionally unavailable URL catches that path.
    git(installed, "remote", "add", "upstream", str(tmp_path / "unavailable-upstream"))
    monkeypatch.setattr(main, "PROJECT_ROOT", installed)
    update_cmd._cmd_update_check("main")
    output = capsys.readouterr().out
    assert "Fetching from origin" in output
    assert "Fetching from upstream" not in output
    assert "Already up to date" in output


def test_distribution_origin_never_enters_fork_auto_sync():
    from hermes_cli.update_cmd_git import OFFICIAL_REPO_URL, _is_fork

    assert not _is_fork(OFFICIAL_REPO_URL)
    assert not _is_fork("git@github.com:yinzhiyan43/hermes-agent.git")
    assert _is_fork("https://github.com/NousResearch/hermes-agent.git")
