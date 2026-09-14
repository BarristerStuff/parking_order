from __future__ import annotations

import itertools
import math
from typing import Iterable


Point = tuple[float, float]
Polygon = list[Point]


class GeometryConfigError(ValueError):
    pass


def as_point(value: Iterable[float]) -> Point:
    items = list(value)
    if len(items) != 2:
        raise GeometryConfigError("POINT_REQUIRES_TWO_COORDINATES")
    x = float(items[0])
    y = float(items[1])
    if not math.isfinite(x) or not math.isfinite(y):
        raise GeometryConfigError("POINT_COORDINATE_NOT_FINITE")
    return (x, y)


def as_polygon(points: Iterable[Iterable[float]]) -> Polygon:
    polygon = [as_point(point) for point in points]
    validate_polygon(polygon)
    return polygon


def validate_polygon(polygon: Polygon, *, require_convex: bool = True) -> None:
    if len(polygon) < 3:
        raise GeometryConfigError("POLYGON_REQUIRES_AT_LEAST_THREE_POINTS")
    if polygon_area(polygon) <= 1e-9:
        raise GeometryConfigError("POLYGON_AREA_DEGENERATE")
    if polygon_self_intersects(polygon):
        raise GeometryConfigError("POLYGON_SELF_INTERSECTS")
    if require_convex and not polygon_is_convex(polygon):
        raise GeometryConfigError("NON_CONVEX_POLYGON_UNSUPPORTED")


def polygon_area(polygon: Polygon) -> float:
    if len(polygon) < 3:
        return 0.0
    signed_area = 0.0
    for index, point in enumerate(polygon):
        next_point = polygon[(index + 1) % len(polygon)]
        signed_area += point[0] * next_point[1] - next_point[0] * point[1]
    return abs(signed_area) / 2.0


def signed_polygon_area(polygon: Polygon) -> float:
    signed_area = 0.0
    for index, point in enumerate(polygon):
        next_point = polygon[(index + 1) % len(polygon)]
        signed_area += point[0] * next_point[1] - next_point[0] * point[1]
    return signed_area / 2.0


def polygon_is_convex(polygon: Polygon) -> bool:
    sign = 0
    count = len(polygon)
    for index in range(count):
        a = polygon[index]
        b = polygon[(index + 1) % count]
        c = polygon[(index + 2) % count]
        cross_value = cross(a, b, c)
        if abs(cross_value) <= 1e-9:
            continue
        current_sign = 1 if cross_value > 0 else -1
        if sign == 0:
            sign = current_sign
        elif sign != current_sign:
            return False
    return True


def polygon_self_intersects(polygon: Polygon) -> bool:
    edges = list(_edges(polygon))
    for first_index, first_edge in enumerate(edges):
        for second_index, second_edge in enumerate(edges):
            if second_index <= first_index:
                continue
            if abs(first_index - second_index) == 1:
                continue
            if first_index == 0 and second_index == len(edges) - 1:
                continue
            if segments_intersect(first_edge[0], first_edge[1], second_edge[0], second_edge[1]):
                return True
    return False


def segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    def orientation(p: Point, q: Point, r: Point) -> float:
        return (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])

    def on_segment(p: Point, q: Point, r: Point) -> bool:
        return min(p[0], r[0]) - 1e-9 <= q[0] <= max(p[0], r[0]) + 1e-9 and min(p[1], r[1]) - 1e-9 <= q[1] <= max(p[1], r[1]) + 1e-9

    o1 = orientation(a, b, c)
    o2 = orientation(a, b, d)
    o3 = orientation(c, d, a)
    o4 = orientation(c, d, b)
    if o1 * o2 < 0 and o3 * o4 < 0:
        return True
    if abs(o1) <= 1e-9 and on_segment(a, c, b):
        return True
    if abs(o2) <= 1e-9 and on_segment(a, d, b):
        return True
    if abs(o3) <= 1e-9 and on_segment(c, a, d):
        return True
    if abs(o4) <= 1e-9 and on_segment(c, b, d):
        return True
    return False


def cross(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def overlap_ratio(subject_polygon: Polygon, roi_polygons: Iterable[Polygon]) -> float:
    validate_polygon(subject_polygon)
    subject_area = polygon_area(subject_polygon)
    intersections = []
    for roi_polygon in roi_polygons:
        validate_polygon(roi_polygon)
        clipped = clip_polygon(subject_polygon, roi_polygon)
        if len(clipped) >= 3 and polygon_area(clipped) > 1e-9:
            intersections.append(clipped)
    if not intersections:
        return 0.0
    union_area = convex_polygons_union_area(intersections)
    return max(0.0, min(1.0, union_area / subject_area))


def convex_polygons_union_area(polygons: list[Polygon]) -> float:
    if len(polygons) > 12:
        raise GeometryConfigError("TOO_MANY_OVERLAPPING_POLYGONS_FOR_EXACT_UNION")
    total = 0.0
    for size in range(1, len(polygons) + 1):
        sign = 1 if size % 2 == 1 else -1
        for combo in itertools.combinations(polygons, size):
            intersection = list(combo[0])
            for clipper in combo[1:]:
                intersection = clip_polygon(intersection, clipper)
                if len(intersection) < 3 or polygon_area(intersection) <= 1e-9:
                    break
            if len(intersection) >= 3:
                total += sign * polygon_area(intersection)
    return max(0.0, total)


def clip_polygon(subject_polygon: Polygon, clip_polygon_points: Polygon) -> Polygon:
    validate_polygon(subject_polygon)
    validate_polygon(clip_polygon_points)
    output_polygon = list(subject_polygon)
    orientation = signed_polygon_area(clip_polygon_points)
    for edge_index, edge_start in enumerate(clip_polygon_points):
        edge_end = clip_polygon_points[(edge_index + 1) % len(clip_polygon_points)]
        input_polygon = output_polygon
        output_polygon = []
        if not input_polygon:
            break
        previous_point = input_polygon[-1]
        for current_point in input_polygon:
            current_inside = inside_half_plane(current_point, edge_start, edge_end, orientation)
            previous_inside = inside_half_plane(previous_point, edge_start, edge_end, orientation)
            if current_inside:
                if not previous_inside:
                    output_polygon.append(line_intersection(previous_point, current_point, edge_start, edge_end))
                output_polygon.append(current_point)
            elif previous_inside:
                output_polygon.append(line_intersection(previous_point, current_point, edge_start, edge_end))
            previous_point = current_point
    return output_polygon


def inside_half_plane(point: Point, edge_start: Point, edge_end: Point, orientation: float) -> bool:
    cross_product = (edge_end[0] - edge_start[0]) * (point[1] - edge_start[1]) - (edge_end[1] - edge_start[1]) * (point[0] - edge_start[0])
    if orientation >= 0:
        return cross_product >= -1e-9
    return cross_product <= 1e-9


def line_intersection(segment_start: Point, segment_end: Point, edge_start: Point, edge_end: Point) -> Point:
    segment_x_delta = segment_end[0] - segment_start[0]
    segment_y_delta = segment_end[1] - segment_start[1]
    edge_x_delta = edge_end[0] - edge_start[0]
    edge_y_delta = edge_end[1] - edge_start[1]
    denominator = segment_x_delta * edge_y_delta - segment_y_delta * edge_x_delta
    if abs(denominator) < 1e-12:
        return segment_end
    scale = ((edge_start[0] - segment_start[0]) * edge_y_delta - (edge_start[1] - segment_start[1]) * edge_x_delta) / denominator
    return (segment_start[0] + scale * segment_x_delta, segment_start[1] + scale * segment_y_delta)


def transform_polygon_homography(polygon: Polygon, matrix: list[list[float]]) -> Polygon:
    validate_homography(matrix)
    transformed = []
    for x, y in polygon:
        denominator = matrix[2][0] * x + matrix[2][1] * y + matrix[2][2]
        if abs(denominator) <= 1e-12:
            raise GeometryConfigError("HOMOGRAPHY_POINT_AT_INFINITY")
        tx = (matrix[0][0] * x + matrix[0][1] * y + matrix[0][2]) / denominator
        ty = (matrix[1][0] * x + matrix[1][1] * y + matrix[1][2]) / denominator
        transformed.append((tx, ty))
    validate_polygon(transformed)
    return transformed


def validate_homography(matrix: object) -> None:
    if not isinstance(matrix, list) or len(matrix) != 3:
        raise GeometryConfigError("HOMOGRAPHY_REQUIRES_3X3_MATRIX")
    for row in matrix:
        if not isinstance(row, list) or len(row) != 3:
            raise GeometryConfigError("HOMOGRAPHY_REQUIRES_3X3_MATRIX")
        for value in row:
            if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise GeometryConfigError("HOMOGRAPHY_VALUE_NOT_FINITE")
    determinant = (
        matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
        - matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
        + matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
    )
    if abs(determinant) <= 1e-12:
        raise GeometryConfigError("HOMOGRAPHY_MATRIX_SINGULAR")


def _edges(polygon: Polygon):
    for index, point in enumerate(polygon):
        yield point, polygon[(index + 1) % len(polygon)]
