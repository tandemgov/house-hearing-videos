"""Tests for committee parsing."""

from src.committees import parse_committees

SAMPLE_YAML = """
- type: house
  name: Committee on the Judiciary
  thomas_id: HSJU
  youtube_id: UCnz99GijBbKAhBo-cOOO7Q
  subcommittees:
    - name: Subcommittee on Courts
      thomas_id: "03"
- type: house
  name: Committee on Agriculture
  thomas_id: HSAG
  subcommittees: []
- type: senate
  name: Committee on Finance
  thomas_id: SSFI
  youtube_id: UCxyz123
"""


class TestParseCommittees:
    def test_filters_house_only(self):
        committees = parse_committees(SAMPLE_YAML)
        thomas_ids = {c.thomas_id for c in committees}
        assert "SSFI" not in thomas_ids

    def test_includes_subcommittees(self):
        committees = parse_committees(SAMPLE_YAML)
        codes = {c.system_code for c in committees}
        assert "hsju03" in codes

    def test_system_code_format(self):
        committees = parse_committees(SAMPLE_YAML)
        hsju = next(c for c in committees if c.thomas_id == "HSJU")
        assert hsju.system_code == "hsju00"

    def test_youtube_id_present(self):
        committees = parse_committees(SAMPLE_YAML)
        hsju = next(c for c in committees if c.thomas_id == "HSJU")
        assert hsju.youtube_id == "UCnz99GijBbKAhBo-cOOO7Q"

    def test_uploads_playlist(self):
        committees = parse_committees(SAMPLE_YAML)
        hsju = next(c for c in committees if c.thomas_id == "HSJU")
        assert hsju.uploads_playlist_id == "UUnz99GijBbKAhBo-cOOO7Q"

    def test_no_youtube_id(self):
        committees = parse_committees(SAMPLE_YAML)
        hsag = next(c for c in committees if c.thomas_id == "HSAG")
        assert hsag.youtube_id is None
        assert hsag.uploads_playlist_id is None
