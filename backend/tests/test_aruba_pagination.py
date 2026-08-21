"""
Tests for ArubaAPIConnector pagination (_fetch_all_pages / _fetch_alerts).

Covers the alert-pagination follow-up tracked in docs/STATUS.md: alerts
were fetched via /central/v1/notifications with a flat limit=100 and no
paging loop, silently truncating alert_severity/alert_count (and therefore
the composite score) once a site crossed 100 open alerts. No test coverage
existed for the Aruba connector before this fix -- this file closes that
gap for the pagination path specifically.

_get() is mocked directly so these tests exercise the pagination loop only
-- no real HTTP calls and no OAuth token flow.

Run from the backend/ directory:
    python -m pytest tests/test_aruba_pagination.py -v
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock

import pytest

from app.services.ingestion import ArubaAPIConnector


@pytest.fixture
def connector():
    return ArubaAPIConnector()


class TestFetchAllPagesLooping:
    def test_single_page_under_limit_stops_immediately(self, connector):
        connector._get = MagicMock(return_value={
            "notifications": [{"id": 1}, {"id": 2}],
            "total": 2,
        })
        results = connector._fetch_all_pages(
            client=None, path="/central/v1/notifications", key="notifications"
        )
        assert results == [{"id": 1}, {"id": 2}]
        assert connector._get.call_count == 1

    def test_multiple_pages_aggregated_via_offset_total(self, connector):
        page1 = {"notifications": [{"id": 1}, {"id": 2}], "total": 3}
        page2 = {"notifications": [{"id": 3}], "total": 3}
        connector._get = MagicMock(side_effect=[page1, page2])

        results = connector._fetch_all_pages(
            client=None, path="/central/v1/notifications", key="notifications"
        )

        assert [r["id"] for r in results] == [1, 2, 3]
        assert connector._get.call_count == 2
        # second call's offset must reflect items already collected
        second_call_params = connector._get.call_args_list[1][0][2]
        assert second_call_params["offset"] == 2

    def test_empty_items_on_first_page_stops_loop(self, connector):
        connector._get = MagicMock(return_value={"notifications": [], "total": 0})
        results = connector._fetch_all_pages(
            client=None, path="/central/v1/notifications", key="notifications"
        )
        assert results == []
        assert connector._get.call_count == 1


class TestFetchAllPagesKeyFallback:
    def test_tuple_key_resolves_to_second_candidate(self, connector):
        connector._get = MagicMock(return_value={"alerts": [{"id": 1}], "total": 1})
        results = connector._fetch_all_pages(
            client=None,
            path="/central/v1/notifications",
            key=("notifications", "alerts"),
        )
        assert results == [{"id": 1}]

    def test_neither_key_present_logs_and_returns_empty(self, connector, caplog):
        connector._get = MagicMock(return_value={"unexpected": []})
        results = connector._fetch_all_pages(
            client=None,
            path="/central/v1/notifications",
            key=("notifications", "alerts"),
        )
        assert results == []
        assert "none of" in caplog.text


class TestFetchAllPagesExtraParams:
    def test_extra_params_merged_into_every_page_request(self, connector):
        page1 = {"notifications": [{"id": 1}], "total": 2}
        page2 = {"notifications": [{"id": 2}], "total": 2}
        connector._get = MagicMock(side_effect=[page1, page2])

        connector._fetch_all_pages(
            client=None,
            path="/central/v1/notifications",
            key="notifications",
            extra_params={"state": "Open"},
        )

        for call in connector._get.call_args_list:
            params = call[0][2]
            assert params["state"] == "Open"


class TestFetchAllPagesSafetyCap:
    def test_stops_at_max_pages_and_warns(self, connector, caplog):
        connector._MAX_PAGES = 3
        # 'total' never catches up to offset -- simulates a misbehaving API
        connector._get = MagicMock(
            return_value={"notifications": [{"id": 1}], "total": 999}
        )

        results = connector._fetch_all_pages(
            client=None, path="/central/v1/notifications", key="notifications"
        )

        assert connector._get.call_count == 3
        assert len(results) == 3
        assert "safety cap" in caplog.text


class TestFetchAlerts:
    def test_fetch_alerts_paginates_and_filters_open(self, connector):
        page1 = {"notifications": [{"id": 1}], "total": 2}
        page2 = {"notifications": [{"id": 2}], "total": 2}
        connector._get = MagicMock(side_effect=[page1, page2])

        alerts = connector._fetch_alerts(client=None)

        assert [a["id"] for a in alerts] == [1, 2]
        for call in connector._get.call_args_list:
            path = call[0][1]
            params = call[0][2]
            assert path == "/central/v1/notifications"
            assert params["state"] == "Open"

    def test_fetch_alerts_swallows_exception_and_returns_empty(self, connector):
        connector._get = MagicMock(side_effect=RuntimeError("boom"))
        assert connector._fetch_alerts(client=None) == []
