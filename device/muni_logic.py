"""Parse 511 arrivals. Runs on CPython and CircuitPython."""


_MONTH_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _is_leap(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _days_before_year(year):
    previous = year - 1
    return 365 * previous + previous // 4 - previous // 100 + previous // 400


def parse_iso_seconds(value):
    """Convert an ISO-8601 timestamp to comparable UTC seconds."""
    text = str(value or "").strip()
    if len(text) < 19 or text[10] != "T":
        raise ValueError("invalid timestamp")

    year = int(text[0:4])
    month = int(text[5:7])
    day = int(text[8:10])
    hour = int(text[11:13])
    minute = int(text[14:16])
    second = int(text[17:19])

    if not 1 <= month <= 12:
        raise ValueError("invalid month")
    month_days = list(_MONTH_DAYS)
    if _is_leap(year):
        month_days[1] = 29
    if not 1 <= day <= month_days[month - 1]:
        raise ValueError("invalid day")

    offset_seconds = 0
    if not text.endswith("Z"):
        plus = text.rfind("+")
        minus = text.rfind("-")
        offset_at = max(plus, minus)
        if offset_at > 18:
            sign = 1 if text[offset_at] == "+" else -1
            offset_hour = int(text[offset_at + 1 : offset_at + 3])
            offset_minute = int(text[offset_at + 4 : offset_at + 6])
            offset_seconds = sign * (offset_hour * 3600 + offset_minute * 60)

    days = _days_before_year(year)
    days += sum(month_days[: month - 1]) + day - 1
    return days * 86400 + hour * 3600 + minute * 60 + second - offset_seconds


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


def _visits(payload):
    """Return each visit with the time 511 built the response."""
    root = payload.get("Siri", payload)
    services = _as_list(root.get("ServiceDelivery"))
    if not services:
        raise ValueError("Missing 511 ServiceDelivery")
    visits = []
    for service in services:
        _check_status(service)
        for delivery in _as_list(service.get("StopMonitoringDelivery")):
            _check_status(delivery)
            responded = _text(service.get("ResponseTimestamp"))
            for visit in _as_list(delivery.get("MonitoredStopVisit")):
                visits.append((visit, responded))
    return visits


def _check_status(delivery):
    status = str(delivery.get("Status")).strip().lower()
    if status in ("false", "0", "failed", "error") or delivery.get("ErrorCondition"):
        raise ValueError("511 StopMonitoring rejected the request")


def _cancelled(journey, call):
    if journey.get("Cancellation") is True:
        return True
    values = (
        journey.get("ProgressStatus"),
        journey.get("JourneyNote"),
        call.get("ArrivalStatus"),
        call.get("DepartureStatus"),
    )
    return any("cancel" in _text(value).lower() for value in values)


def _arrival_time(call):
    for key in (
        "ExpectedArrivalTime",
        "ExpectedDepartureTime",
        "AimedArrivalTime",
        "AimedDepartureTime",
    ):
        value = _text(call.get(key))
        if value:
            return value
    return ""


def parse_remaining_seconds(payload, route, limit=2):
    """Return arrival seconds measured from the response time.

    The vehicle's recorded time is a fallback. It can be minutes old.
    """
    arrivals = []
    seen = set()

    for visit, responded in _visits(payload):
        journey = visit.get("MonitoredVehicleJourney") or {}
        if _text(journey.get("LineRef")) != route:
            continue
        call = journey.get("MonitoredCall") or {}
        if _cancelled(journey, call):
            continue

        reference = responded or _text(visit.get("RecordedAtTime"))
        expected = _arrival_time(call)
        if not reference or not expected:
            continue
        try:
            remaining = parse_iso_seconds(expected) - parse_iso_seconds(reference)
        except (TypeError, ValueError):
            continue
        if remaining < -30 or remaining > 10800:
            continue

        framed = journey.get("FramedVehicleJourneyRef") or {}
        journey_ref = _text(framed.get("DatedVehicleJourneyRef"))
        vehicle_ref = _text(journey.get("VehicleRef"))
        key = (journey_ref or vehicle_ref or expected, expected)
        if key in seen:
            continue
        seen.add(key)
        arrivals.append(remaining)

    arrivals.sort()
    return arrivals[:limit]


def eta_text(arrivals, age_seconds=0):
    """Render arrival minutes using whole-minute truncation."""
    values = []
    for initial_seconds in arrivals:
        seconds = initial_seconds - age_seconds
        if seconds < -30:
            continue
        values.append("DUE" if seconds < 60 else str(int(seconds // 60)))
    return " ".join(values) if values else "--"


def arrival_pair_texts(arrivals, age_seconds=0):
    """Return the next countdown and following arrival as separate fields."""
    remaining = []
    for initial_seconds in arrivals:
        seconds = int(initial_seconds - age_seconds)
        if seconds < -30:
            continue
        remaining.append(seconds)
        if len(remaining) == 2:
            break

    if not remaining:
        return "--", ""

    first = remaining[0]
    if first < 60:
        first_text = "DUE"
    else:
        minutes, seconds = divmod(first, 60)
        first_text = "99+" if minutes > 99 else str(minutes) + ":" + ("%02d" % seconds)

    if len(remaining) == 1:
        return first_text, ""

    second = remaining[1]
    if second < 60:
        second_text = "DUE"
    else:
        minutes = second // 60
        second_text = "99" if minutes > 99 else str(minutes)
    return first_text, second_text
