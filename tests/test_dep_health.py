"""Tests for dependency-diligence/scripts/dep_health.py.

Registry payloads are fixtures: the tests must not depend on the network, and
asserting against a live registry would test today's PyPI, not the summarizer.
"""

from __future__ import annotations

import datetime as dt
import unittest

from support import load_script

script = load_script("dependency-diligence", "dep_health.py")

NOW = dt.datetime(2026, 8, 7, tzinfo=dt.timezone.utc)

PYPI_PAYLOAD = {
    "info": {
        "name": "examplelib",
        "version": "2.1.0",
        "summary": "An example library.",
        "license": "",
        "classifiers": ["License :: OSI Approved :: MIT License"],
        "requires_dist": ["urllib3<3,>=1.26", "idna<4,>=2.5; python_version>'3'"],
        "requires_python": ">=3.9",
        "project_urls": {"Homepage": "https://example.org", "Source": "https://github.com/acme/examplelib"},
    },
    "releases": {
        "1.0.0": [{"upload_time_iso_8601": "2020-01-01T00:00:00.000000Z"}],
        "2.0.0": [{"upload_time_iso_8601": "2026-01-05T00:00:00.000000Z"}],
        "2.1.0": [
            {"upload_time_iso_8601": "2026-06-01T00:00:00.000000Z"},
            {"upload_time_iso_8601": "2026-06-01T00:05:00.000000Z"},
        ],
    },
}

NPM_PAYLOAD = {
    "name": "example-pkg",
    "description": "An example package.",
    "license": "MIT",
    "homepage": "https://example.org",
    "repository": {"type": "git", "url": "git+ssh://git@github.com/acme/example-pkg.git"},
    "dist-tags": {"latest": "1.3.0"},
    "time": {
        "created": "2016-01-01T00:00:00.000Z",
        "1.0.0": "2016-01-01T00:00:00.000Z",
        "1.3.0": "2018-04-09T00:00:00.000Z",
    },
    "versions": {"1.3.0": {"dependencies": {"ms": "^2.0.0"}, "deprecated": "use something else"}},
}


class ParsingTest(unittest.TestCase):
    def test_iso_parsing_handles_z_suffix_and_naive_stamps(self):
        self.assertEqual(script.parse_iso("2026-01-01T00:00:00Z").year, 2026)
        self.assertIsNotNone(script.parse_iso("2026-01-01T00:00:00").tzinfo)
        self.assertIsNone(script.parse_iso(None))
        self.assertIsNone(script.parse_iso("not a date"))

    def test_days_since(self):
        self.assertEqual(script.days_since(NOW - dt.timedelta(days=10), NOW), 10)
        self.assertIsNone(script.days_since(None, NOW))


class PypiSummaryTest(unittest.TestCase):
    def setUp(self):
        self.summary = script.summarize_pypi(PYPI_PAYLOAD, NOW)

    def test_core_fields(self):
        self.assertEqual(self.summary["name"], "examplelib")
        self.assertEqual(self.summary["latestVersion"], "2.1.0")
        self.assertEqual(self.summary["releaseCount"], 3)

    def test_license_falls_back_to_classifiers(self):
        self.assertEqual(self.summary["license"], "MIT License")

    def test_repository_read_from_project_urls(self):
        self.assertEqual(self.summary["repository"], "https://github.com/acme/examplelib")

    def test_release_dates_use_the_earliest_file_of_a_version(self):
        self.assertEqual(self.summary["latestRelease"], "2026-06-01")
        self.assertEqual(self.summary["firstRelease"], "2020-01-01")

    def test_releases_last_year_counts_the_window(self):
        self.assertEqual(self.summary["releasesLastYear"], 2)

    def test_dependency_names_are_stripped_of_specifiers(self):
        self.assertIn("urllib3", self.summary["dependencyNames"])
        self.assertIn("idna", self.summary["dependencyNames"])
        self.assertEqual(self.summary["directDependencies"], 2)


class NpmSummaryTest(unittest.TestCase):
    def setUp(self):
        self.summary = script.summarize_npm(NPM_PAYLOAD, NOW)

    def test_core_fields(self):
        self.assertEqual(self.summary["name"], "example-pkg")
        self.assertEqual(self.summary["latestVersion"], "1.3.0")
        self.assertEqual(self.summary["releaseCount"], 2)

    def test_created_and_modified_are_not_versions(self):
        self.assertEqual(self.summary["firstRelease"], "2016-01-01")
        self.assertEqual(self.summary["latestRelease"], "2018-04-09")

    def test_deprecation_is_surfaced(self):
        self.assertTrue(self.summary["deprecated"])

    def test_repository_object_is_flattened(self):
        self.assertIn("github.com/acme/example-pkg", self.summary["repository"])


class ObservationsTest(unittest.TestCase):
    def test_stale_package_is_flagged(self):
        notes = script.observations(script.summarize_npm(NPM_PAYLOAD, NOW), None)
        self.assertTrue(any("no release in" in note for note in notes))
        self.assertTrue(any("deprecated" in note for note in notes))

    def test_healthy_package_is_quiet(self):
        notes = script.observations(script.summarize_pypi(PYPI_PAYLOAD, NOW), None)
        self.assertEqual(notes, [], notes)

    def test_missing_license_is_flagged(self):
        payload = json_copy(PYPI_PAYLOAD)
        payload["info"]["classifiers"] = []
        notes = script.observations(script.summarize_pypi(payload, NOW), None)
        self.assertTrue(any("license" in note for note in notes))

    def test_wide_dependency_fan_out_is_flagged(self):
        payload = json_copy(PYPI_PAYLOAD)
        payload["info"]["requires_dist"] = [f"dep{i}" for i in range(12)]
        notes = script.observations(script.summarize_pypi(payload, NOW), None)
        self.assertTrue(any("direct dependencies" in note for note in notes))

    def test_repository_signals(self):
        summary = script.summarize_pypi(PYPI_PAYLOAD, NOW)
        notes = script.observations(
            summary, {"archived": True, "contributors": 1, "daysSinceLastPush": 900}
        )
        self.assertTrue(any("archived" in note for note in notes))
        self.assertTrue(any("bus factor" in note for note in notes))
        self.assertTrue(any("no commits" in note for note in notes))


def json_copy(payload: dict) -> dict:
    import json

    return json.loads(json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
