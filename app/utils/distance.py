import math
from typing import Tuple


def haversine_distance(
    coord1: Tuple[float, float],
    coord2: Tuple[float, float],
) -> float:
    lat1, lon1 = coord1
    lat2, lon2 = coord2

    R = 6371.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def point_to_segment_distance(
    point: Tuple[float, float],
    seg_start: Tuple[float, float],
    seg_end: Tuple[float, float],
) -> float:
    px, py = point
    x1, y1 = seg_start
    x2, y2 = seg_end

    dx = x2 - x1
    dy = y2 - y1

    if dx == 0 and dy == 0:
        return haversine_distance(point, seg_start) * 1000

    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0, min(1, t))

    nearest_x = x1 + t * dx
    nearest_y = y1 + t * dy

    return haversine_distance(point, (nearest_x, nearest_y)) * 1000


def calculate_path_deviation(
    current_point: Tuple[float, float],
    route_points: list,
) -> float:
    if not route_points or len(route_points) < 2:
        return 0.0

    min_distance = float("inf")
    for i in range(len(route_points) - 1):
        dist = point_to_segment_distance(
            current_point,
            route_points[i],
            route_points[i + 1],
        )
        min_distance = min(min_distance, dist)

    return min_distance
