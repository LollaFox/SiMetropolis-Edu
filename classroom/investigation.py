"""Shared schematic geometry for the Long Valley classroom sites."""

from dataclasses import dataclass


STATIONS = ((70, 210), (650, 210))
ALIGNMENTS = {"central": 210, "north": 112, "south": 288}
ACCESS_ROUTES = ("east", "valley")
WETLAND_TOP = {"A": 160, "B": 62}
MAP_BOTTOM = 344


@dataclass(frozen=True)
class Design:
    alignment: str = "central"
    crossing_type: str = "elevated"
    access_route: str = "east"


@dataclass(frozen=True)
class Footprint:
    x: int
    y: int
    width: int
    height: int

    def overlap(self, other):
        x = max(self.x, other.x)
        y = max(self.y, other.y)
        right = min(self.x + self.width, other.x + other.width)
        bottom = min(self.y + self.height, other.y + other.height)
        if right > x and bottom > y:
            return Footprint(x, y, right - x, bottom - y)
        return None


@dataclass(frozen=True)
class CrossingGeometry:
    surface_lines: tuple
    tunnel_lines: tuple
    works: dict


def elevated_crossing(points, access):
    _, (west_end, y), (east_end, _), _ = points
    supports = tuple(Footprint(x - 6, y - 6, 12, 12) for x in range(west_end, east_end + 1, 100))
    return CrossingGeometry(
        surface_lines=(points,), tunnel_lines=(), works={"access": access, "supports": supports},
    )


def tunnel_crossing(points, access):
    portals = points[1:3]
    entrances = tuple(Footprint(x - 11, y - 9, 22, 18) for x, y in portals)
    return CrossingGeometry(
        surface_lines=(points[:2], points[2:]), tunnel_lines=(portals,),
        works={"access": access, "entrances": entrances},
    )


CROSSING_TYPES = {"elevated": elevated_crossing, "tunnel": tunnel_crossing}


def crossing_geometry(design):
    y = ALIGNMENTS[design.alignment]
    west, east = STATIONS
    east_end = 560
    points = (west, (160, y), (east_end, y), east)
    access = access_footprint(design.access_route, east_end, y)
    return CROSSING_TYPES[design.crossing_type](points, access)


def access_footprint(route, east_end, y):
    # Both approaches serve the east work area, entering from the south.
    east_x = east_end - 6
    if route == "east":
        return (Footprint(east_x, y, 12, MAP_BOTTOM - y),)
    # The turn runs alongside the railway so both paths can be traced on the map.
    turn_x = 354
    turn_y = y + 18
    return (
        Footprint(turn_x, turn_y + 12, 12, MAP_BOTTOM - turn_y - 12),
        Footprint(turn_x, turn_y, east_x + 12 - turn_x, 12),
        Footprint(east_x, y, 12, turn_y - y),
    )


def nesting_habitat(site):
    return Footprint(275, WETLAND_TOP[site] + 20, 170, 57)


def overlapping_works(works, habitat):
    overlaps = {}
    for work, footprints in works.items():
        for footprint in footprints:
            overlap = footprint.overlap(habitat)
            if overlap is not None:
                overlaps.setdefault(work, []).append(overlap)
    return overlaps
