from pathlib import Path

from edward.config.application_settings import ApplicationSettings, ApplicationSettingsStore


def test_settings_store_creates_default_storage_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    store = ApplicationSettingsStore(tmp_path / "config" / "settings.json")

    settings = store.load()

    assert Path(settings.storage_path) == (tmp_path / "data").resolve()


def test_settings_store_persists_storage_path(tmp_path):
    config = tmp_path / "config" / "settings.json"
    selected = tmp_path / "edward-data"
    store = ApplicationSettingsStore(config)

    store.save(ApplicationSettings(str(selected)))

    loaded = store.load()
    assert Path(loaded.storage_path) == selected.resolve()
    assert selected.is_dir()
    assert config.is_file()


def test_settings_store_recovers_from_invalid_json(tmp_path):
    config = tmp_path / "config" / "settings.json"
    config.parent.mkdir(parents=True)
    config.write_text("not json", encoding="utf-8")
    store = ApplicationSettingsStore(config)

    loaded = store.load()

    assert Path(loaded.storage_path) == (Path.cwd() / "data").resolve()
