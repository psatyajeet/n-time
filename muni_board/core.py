"""Parse 511 responses and build the board data for the laptop preview."""

class PayloadError(RuntimeError):
    """511 returned a response that reports a failure."""


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _text(value):
    if value is None:
        return ""
    if isinstance(value, list):
        return _text(value[0]) if value else ""
    if isinstance(value, dict):
        for key in ("value", "Value", "text", "Text"):
            if key in value:
                return _text(value[key])
        return ""
    return str(value).strip()


def _status_failed(value):
    if value is None or value == "":
        return False
    if value is False or value == 0:
        return True
    return str(value).strip().lower() in ("false", "0", "failed", "error")


def _service_deliveries(payload):
    root = payload.get("Siri", payload)
    deliveries = _as_list(root.get("ServiceDelivery"))
    if not deliveries:
        raise PayloadError("511 response has no ServiceDelivery")
    return deliveries


def monitored_visits(payload):
    visits = []
    for service in _service_deliveries(payload):
        if _status_failed(service.get("Status")):
            raise PayloadError("511 ServiceDelivery status is false")
        if service.get("ErrorCondition"):
            raise PayloadError("511 ServiceDelivery contains an error")
        for delivery in _as_list(service.get("StopMonitoringDelivery")):
            if _status_failed(delivery.get("Status")) or delivery.get("ErrorCondition"):
                raise PayloadError("511 StopMonitoringDelivery status is false")
            visits.extend(_as_list(delivery.get("MonitoredStopVisit")))
    return visits


def _is_cancelled(journey, call):
    status_values = (
        journey.get("ProgressStatus"),
        journey.get("JourneyNote"),
        call.get("ArrivalStatus"),
        call.get("DepartureStatus"),
    )
    if journey.get("Cancellation") is True:
        return True
    return any("cancel" in _text(value).lower() for value in status_values)


def route_choices(payload):
    """Return the route IDs and destinations reported at a stop."""
    routes = {}
    for visit in monitored_visits(payload):
        journey = visit.get("MonitoredVehicleJourney") or {}
        route = _text(journey.get("LineRef"))
        call = journey.get("MonitoredCall") or {}
        if route and not _is_cancelled(journey, call):
            destinations = routes.setdefault(route, set())
            destination = _text(journey.get("DestinationName") or call.get("DestinationDisplay"))
            if destination:
                destinations.add(destination)
    return {route: sorted(destinations) for route, destinations in sorted(routes.items())}


def _selected_time(call):
    for key in (
        "ExpectedArrivalTime",
        "ExpectedDepartureTime",
        "AimedArrivalTime",
        "AimedDepartureTime",
    ):
        value = _text(call.get(key))
        if value:
            return value, key
    return "", ""


def _journey_key(journey, eta_epoch, destination):
    framed = journey.get("FramedVehicleJourneyRef") or {}
    data_frame = _text(framed.get("DataFrameRef"))
    journey_ref = _text(framed.get("DatedVehicleJourneyRef"))
    vehicle_ref = _text(journey.get("VehicleRef"))
    stable_ref = journey_ref or vehicle_ref
    if stable_ref:
        return data_frame, stable_ref, eta_epoch
    return destination, eta_epoch


def parse_arrivals(payload, stop, now_epoch, parse_time, limit=2):
    """Return sorted, deduplicated arrivals for one configured platform."""
    arrivals = []
    seen = set()

    for visit in monitored_visits(payload):
        journey = visit.get("MonitoredVehicleJourney") or {}
        if _text(journey.get("LineRef")) != stop["route"]:
            continue

        call = journey.get("MonitoredCall") or {}
        if _is_cancelled(journey, call):
            continue

        raw_time, time_kind = _selected_time(call)
        if not raw_time:
            continue
        try:
            eta_epoch = parse_time(raw_time)
        except (TypeError, ValueError):
            continue
        if eta_epoch is None or eta_epoch < now_epoch - 30:
            continue

        destination = _text(journey.get("DestinationName"))
        if not destination:
            destination = _text(call.get("DestinationDisplay")) or "Destination unavailable"

        key = _journey_key(journey, eta_epoch, destination)
        if key in seen:
            continue
        seen.add(key)

        recorded_raw = _text(visit.get("RecordedAtTime"))
        try:
            recorded_epoch = parse_time(recorded_raw) if recorded_raw else None
        except (TypeError, ValueError):
            recorded_epoch = None

        arrivals.append(
            {
                "route": stop["route"],
                "direction": stop["key"],
                "direction_ref": _text(journey.get("DirectionRef")),
                "stop_code": stop["stop_code"],
                "destination": destination,
                "eta_epoch": eta_epoch,
                "recorded_epoch": recorded_epoch,
                "time_kind": time_kind,
            }
        )

    arrivals.sort(key=lambda arrival: arrival["eta_epoch"])
    return arrivals[:limit]


def build_board(payloads, settings, now_epoch, parse_time, errors=None):
    directions = {}
    for stop in settings["stops"]:
        payload = payloads.get(stop["key"])
        arrivals = [] if payload is None else parse_arrivals(payload, stop, now_epoch, parse_time)
        directions[stop["key"]] = {**stop, "arrivals": arrivals}

    return {
        "badge": settings["badge"],
        "title": settings["title"],
        "generated_epoch": now_epoch,
        "directions": directions,
        "errors": errors or {},
        "attribution": "Data: 511 SF Bay",
    }


def minutes_until(eta_epoch, now_epoch):
    seconds = eta_epoch - now_epoch
    if seconds < 60:
        return 0
    return int(seconds // 60)
