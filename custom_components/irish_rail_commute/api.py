"""Irish Rail API client."""
from __future__ import annotations

from datetime import datetime
import requests
import xml.etree.ElementTree as ET


class IrishRailAPI:
    """Simple client for Irish Rail realtime API."""

    BASE_URL = "https://api.irishrail.ie/realtime/realtime.asmx"

    def __init__(self) -> None:
        self.session = requests.Session()

    def _get_xml(self, endpoint: str, params: dict | None = None) -> ET.Element:
        """Fetch and parse XML from Irish Rail."""
        url = f"{self.BASE_URL}/{endpoint}"
        response = self.session.get(url, params=params, timeout=15)
        response.raise_for_status()
        return ET.fromstring(response.content)

    def _clean_text(self, value: str | None) -> str | None:
        """Return stripped text or None."""
        if value is None:
            return None
        value = value.strip()
        return value or None

    def _safe_int(self, value: str | None, default: int = 0) -> int:
        """Parse int safely."""
        try:
            return int((value or "").strip())
        except (TypeError, ValueError):
            return default

    def get_all_stations(self) -> list[dict]:
        """Return all stations as [{'name': ..., 'code': ...}, ...]."""
        root = self._get_xml("getAllStationsXML")

        stations: list[dict] = []

        for elem in root.iter():
            if elem.tag.endswith("objStation"):
                name = None
                code = None

                for child in elem:
                    tag = child.tag.split("}")[-1]
                    text = (child.text or "").strip()

                    if tag == "StationDesc":
                        name = text
                    elif tag == "StationCode":
                        code = text.upper()

                if name and code:
                    stations.append(
                        {
                            "name": name,
                            "code": code,
                        }
                    )

        seen = set()
        unique = []
        for s in stations:
            key = (s["code"], s["name"])
            if key not in seen:
                seen.add(key)
                unique.append(s)

        unique.sort(key=lambda x: x["name"])
        return unique

    def get_station_departures(self, station_code: str, minutes: int = 90) -> list[dict]:
        """Return departures for a station."""
        root = self._get_xml(
            "getStationDataByCodeXML_WithNumMins",
            {"StationCode": station_code, "NumMins": minutes},
        )

        trains: list[dict] = []

        for elem in root.iter():
            if elem.tag.endswith("objStationData"):
                row: dict[str, str] = {}

                for child in elem:
                    tag = child.tag.split("}")[-1]
                    row[tag] = (child.text or "").strip()

                late = self._safe_int(row.get("Late"), 0)

                trains.append(
                    {
                        "train_code": self._clean_text(row.get("Traincode")),
                        "train_date": self._clean_text(row.get("Traindate")),
                        "origin": self._clean_text(row.get("Origin")),
                        "destination": self._clean_text(row.get("Destination")),
                        "direction": self._clean_text(row.get("Direction")),
                        "scheduled_departure": self._clean_text(row.get("Schdepart")),
                        "expected_departure": self._clean_text(row.get("Expdepart")),
                        "scheduled_arrival": self._clean_text(row.get("Scharrival")),
                        "expected_arrival": self._clean_text(row.get("Exparrival")),
                        "late": late,
                        "status": self._clean_text(row.get("Status")),
                    }
                )

        return trains

    def get_current_trains(self) -> list[dict]:
        """Return currently running trains with code/date info."""
        root = self._get_xml("getCurrentTrainsXML")
        trains: list[dict] = []

        for elem in root.iter():
            if elem.tag.endswith("objTrainPositions"):
                row: dict[str, str] = {}

                for child in elem:
                    tag = child.tag.split("}")[-1]
                    row[tag] = (child.text or "").strip()

                trains.append(
                    {
                        "train_code": self._clean_text(row.get("TrainCode")),
                        "train_date": self._clean_text(row.get("TrainDate")),
                        "status": self._clean_text(row.get("TrainStatus")),
                        "latitude": self._clean_text(row.get("TrainLatitude")),
                        "longitude": self._clean_text(row.get("TrainLongitude")),
                        "public_message": self._clean_text(row.get("PublicMessage")),
                        "direction": self._clean_text(row.get("Direction")),
                    }
                )

        return trains

    def get_train_movements(self, train_code: str, train_date: str) -> list[dict]:
        """Return stop-by-stop train movements for a specific train."""
        root = self._get_xml(
            "getTrainMovementsXML",
            {"TrainId": train_code, "TrainDate": train_date},
        )

        movements: list[dict] = []

        for elem in root.iter():
            if elem.tag.endswith("objTrainMovements"):
                row: dict[str, str] = {}

                for child in elem:
                    tag = child.tag.split("}")[-1]
                    row[tag] = (child.text or "").strip()

                movements.append(
                    {
                        "train_code": self._clean_text(row.get("TrainCode")),
                        "train_date": self._clean_text(row.get("TrainDate")),
                        "location_code": self._clean_text(row.get("LocationCode")),
                        "location_name": (
                            self._clean_text(row.get("LocationFullName"))
                            or self._clean_text(row.get("LocationCode"))
                        ),
                        "location_order": self._safe_int(row.get("LocationOrder"), 0),
                        "location_type": self._clean_text(row.get("LocationType")),
                        "train_origin": self._clean_text(row.get("TrainOrigin")),
                        "train_destination": self._clean_text(row.get("TrainDestination")),
                        "scheduled_arrival": self._clean_text(row.get("ScheduledArrival")),
                        "scheduled_departure": self._clean_text(row.get("ScheduledDeparture")),
                        "expected_arrival": self._clean_text(row.get("ExpectedArrival")),
                        "expected_departure": self._clean_text(row.get("ExpectedDeparture")),
                        "actual_arrival": self._clean_text(row.get("Arrival")),
                        "actual_departure": self._clean_text(row.get("Departure")),
                        "auto_arrival": self._clean_text(row.get("AutoArrival")),
                        "auto_depart": self._clean_text(row.get("AutoDepart")),
                        "stop_type": self._clean_text(row.get("StopType")),
                    }
                )

        movements.sort(key=lambda x: x.get("location_order", 0))
        return movements

    def resolve_train_date(self, train_code: str) -> str | None:
        """Resolve train date for a running train from current trains."""
        for train in self.get_current_trains():
            if train.get("train_code") == train_code:
                return train.get("train_date")
        return None

    def get_route_segment(
        self,
        train_code: str,
        train_date: str,
        origin_code: str,
        destination_code: str,
    ) -> dict | None:
        """Return just the stop segment between origin and destination."""
        movements = self.get_train_movements(train_code, train_date)
        if not movements:
            return None

        origin_idx = None
        destination_idx = None

        for idx, stop in enumerate(movements):
            code = (stop.get("location_code") or "").upper()
            if origin_idx is None and code == origin_code.upper():
                origin_idx = idx
            if code == destination_code.upper():
                destination_idx = idx
                if origin_idx is not None and destination_idx >= origin_idx:
                    break

        if origin_idx is None or destination_idx is None or destination_idx < origin_idx:
            return None

        segment = movements[origin_idx : destination_idx + 1]
        destination_stop = segment[-1]

        return {
            "train_code": train_code,
            "train_date": train_date,
            "origin_stop": segment[0],
            "destination_stop": destination_stop,
            "segment_stops": segment,
            "segment_stop_count": len(segment),
            "scheduled_arrival": destination_stop.get("scheduled_arrival"),
            "expected_arrival": destination_stop.get("expected_arrival"),
            "arrival_time": destination_stop.get("expected_arrival")
            or destination_stop.get("scheduled_arrival"),
        }