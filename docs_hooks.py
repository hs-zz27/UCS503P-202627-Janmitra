"""Include shared assets without relying on Windows symlink support."""

from pathlib import Path

from mkdocs.structure.files import File


def on_files(files, config):
    root = Path(config.config_file_path).parent
    for item in list(files):
        if item.src_uri == "assets":
            files.remove(item)
    for asset in (root / "assets").rglob("*"):
        if asset.is_file():
            files.append(
                File(
                    asset.relative_to(root).as_posix(),
                    str(root),
                    config.site_dir,
                    config.use_directory_urls,
                )
            )
    return files
