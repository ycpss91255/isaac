"""Unit tests for import_model.py — host-runnable, no Isaac Sim required.

Tests cover: path resolution, existing file checks, material template
generation, root composition generation, and output validation.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "script"))
import import_model


@pytest.fixture
def tmp_model(tmp_path):
    """Create a minimal URDF and output dir for testing."""
    urdf_dir = tmp_path / "urdf"
    urdf_dir.mkdir()
    urdf_file = urdf_dir / "test_robot.urdf"
    urdf_file.write_text("<robot name='test'/>")

    out_dir = tmp_path / "usd" / "robot" / "test_robot"
    return {"urdf": urdf_file, "out_dir": out_dir, "name": "test_robot"}


class TestResolvePaths:
    def test_returns_all_expected_keys(self, tmp_model):
        args = SimpleNamespace(
            urdf=str(tmp_model["urdf"]),
            output=str(tmp_model["out_dir"]),
            name=tmp_model["name"],
        )
        paths = import_model._resolve_paths(args)
        assert set(paths.keys()) == {
            "urdf", "out_dir", "root", "geometry", "material", "textures",
        }

    def test_paths_use_name_prefix(self, tmp_model):
        args = SimpleNamespace(
            urdf=str(tmp_model["urdf"]),
            output=str(tmp_model["out_dir"]),
            name="mybot",
        )
        paths = import_model._resolve_paths(args)
        assert paths["root"].name == "mybot.usd"
        assert paths["geometry"].name == "mybot_geometry.usda"
        assert paths["material"].name == "mybot_material.usda"
        assert paths["textures"].name == "textures"

    def test_urdf_not_found_exits(self, tmp_path):
        args = SimpleNamespace(
            urdf=str(tmp_path / "nonexistent.urdf"),
            output=str(tmp_path / "out"),
            name="x",
        )
        with pytest.raises(SystemExit):
            import_model._resolve_paths(args)

    def test_paths_are_absolute(self, tmp_model):
        args = SimpleNamespace(
            urdf=str(tmp_model["urdf"]),
            output=str(tmp_model["out_dir"]),
            name="test_robot",
        )
        paths = import_model._resolve_paths(args)
        for key, p in paths.items():
            assert Path(p).is_absolute(), f"{key} is not absolute: {p}"


class TestCheckExisting:
    def test_blocks_when_geometry_exists_no_force(self, tmp_model):
        out_dir = tmp_model["out_dir"]
        out_dir.mkdir(parents=True)
        geom = out_dir / "test_robot_geometry.usda"
        geom.write_text("existing")

        paths = {
            "root": out_dir / "test_robot.usd",
            "geometry": geom,
        }
        with pytest.raises(SystemExit):
            import_model._check_existing(paths, force=False)

    def test_allows_when_geometry_exists_with_force(self, tmp_model):
        out_dir = tmp_model["out_dir"]
        out_dir.mkdir(parents=True)
        geom = out_dir / "test_robot_geometry.usda"
        geom.write_text("existing")

        paths = {
            "root": out_dir / "test_robot.usd",
            "geometry": geom,
        }
        import_model._check_existing(paths, force=True)

    def test_allows_when_no_existing_files(self, tmp_model):
        out_dir = tmp_model["out_dir"]
        paths = {
            "root": out_dir / "test_robot.usd",
            "geometry": out_dir / "test_robot_geometry.usda",
        }
        import_model._check_existing(paths, force=False)


class TestEnsureDirs:
    def test_creates_output_and_textures(self, tmp_model):
        paths = {
            "out_dir": tmp_model["out_dir"],
            "textures": tmp_model["out_dir"] / "textures",
        }
        assert not paths["out_dir"].exists()
        import_model._ensure_dirs(paths)
        assert paths["out_dir"].is_dir()
        assert paths["textures"].is_dir()


class TestWriteMaterialTemplate:
    def test_creates_template_when_missing(self, tmp_model):
        out_dir = tmp_model["out_dir"]
        out_dir.mkdir(parents=True)
        paths = {
            "geometry": out_dir / "test_robot_geometry.usda",
            "material": out_dir / "test_robot_material.usda",
        }
        import_model._write_material_template(paths)

        content = paths["material"].read_text()
        assert "#usda 1.0" in content
        assert "@./test_robot_geometry.usda@" in content

    def test_preserves_existing_material(self, tmp_model):
        out_dir = tmp_model["out_dir"]
        out_dir.mkdir(parents=True)
        paths = {
            "geometry": out_dir / "test_robot_geometry.usda",
            "material": out_dir / "test_robot_material.usda",
        }
        paths["material"].write_text("custom material content")
        import_model._write_material_template(paths)

        assert paths["material"].read_text() == "custom material content"

    def test_sublayer_references_geometry(self, tmp_model):
        out_dir = tmp_model["out_dir"]
        out_dir.mkdir(parents=True)
        paths = {
            "geometry": out_dir / "bot_geometry.usda",
            "material": out_dir / "bot_material.usda",
        }
        import_model._write_material_template(paths)

        content = paths["material"].read_text()
        assert "@./bot_geometry.usda@" in content


class TestWriteRootComposition:
    def test_creates_root_file(self, tmp_model):
        out_dir = tmp_model["out_dir"]
        out_dir.mkdir(parents=True)
        paths = {
            "root": out_dir / "test_robot.usd",
            "material": out_dir / "test_robot_material.usda",
        }
        import_model._write_root_composition(paths)

        content = paths["root"].read_text()
        assert "#usda 1.0" in content
        assert "@./test_robot_material.usda@" in content

    def test_sublayer_chain_is_correct(self, tmp_model):
        out_dir = tmp_model["out_dir"]
        out_dir.mkdir(parents=True)
        paths = {
            "root": out_dir / "r.usd",
            "material": out_dir / "r_material.usda",
        }
        import_model._write_root_composition(paths)
        content = paths["root"].read_text()
        assert "@./r_material.usda@" in content


class TestValidateOutput:
    def test_passes_when_all_exist(self, tmp_model):
        out_dir = tmp_model["out_dir"]
        out_dir.mkdir(parents=True)
        (out_dir / "textures").mkdir()

        paths = {
            "root": out_dir / "a.usd",
            "geometry": out_dir / "a_geometry.usda",
            "material": out_dir / "a_material.usda",
            "textures": out_dir / "textures",
        }
        for key in ("root", "geometry", "material"):
            paths[key].write_text("x")

        assert import_model._validate_output(paths) is True

    def test_fails_when_geometry_missing(self, tmp_model):
        out_dir = tmp_model["out_dir"]
        out_dir.mkdir(parents=True)
        (out_dir / "textures").mkdir()

        paths = {
            "root": out_dir / "a.usd",
            "geometry": out_dir / "a_geometry.usda",
            "material": out_dir / "a_material.usda",
            "textures": out_dir / "textures",
        }
        paths["root"].write_text("x")
        paths["material"].write_text("x")

        assert import_model._validate_output(paths) is False

    def test_fails_when_textures_dir_missing(self, tmp_model):
        out_dir = tmp_model["out_dir"]
        out_dir.mkdir(parents=True)

        paths = {
            "root": out_dir / "a.usd",
            "geometry": out_dir / "a_geometry.usda",
            "material": out_dir / "a_material.usda",
            "textures": out_dir / "textures",
        }
        for key in ("root", "geometry", "material"):
            paths[key].write_text("x")

        assert import_model._validate_output(paths) is False
