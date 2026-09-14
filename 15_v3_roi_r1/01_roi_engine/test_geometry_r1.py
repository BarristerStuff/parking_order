from geometry import GeometryConfigError, as_polygon, overlap_ratio, polygon_area, transform_polygon_homography


def assert_almost_equal(actual, expected, tolerance=1e-6):
    assert abs(actual - expected) <= tolerance, (actual, expected)


def test_polygon_area_rectangle():
    assert_almost_equal(polygon_area(as_polygon([[0, 0], [10, 0], [10, 5], [0, 5]])), 50.0)


def test_overlap_union_does_not_double_count_overlapping_roi_polygons():
    subject = as_polygon([[0, 0], [10, 0], [10, 10], [0, 10]])
    roi_a = as_polygon([[0, 0], [8, 0], [8, 10], [0, 10]])
    roi_b = as_polygon([[2, 0], [10, 0], [10, 10], [2, 10]])
    assert_almost_equal(overlap_ratio(subject, [roi_a, roi_b]), 1.0)


def test_non_convex_polygon_rejected():
    try:
        as_polygon([[0, 0], [4, 0], [2, 1], [4, 4], [0, 4]])
    except GeometryConfigError as exc:
        assert "NON_CONVEX_POLYGON_UNSUPPORTED" in str(exc)
    else:
        raise AssertionError("non-convex polygon should be rejected")


def test_degenerate_polygon_rejected():
    try:
        as_polygon([[0, 0], [1, 1], [2, 2]])
    except GeometryConfigError as exc:
        assert "POLYGON_AREA_DEGENERATE" in str(exc)
    else:
        raise AssertionError("degenerate polygon should be rejected")


def test_empty_polygon_rejected():
    try:
        as_polygon([])
    except GeometryConfigError as exc:
        assert "POLYGON_REQUIRES_AT_LEAST_THREE_POINTS" in str(exc)
    else:
        raise AssertionError("empty polygon should be rejected")


def test_homography_transforms_image_to_bev():
    polygon = as_polygon([[10, 10], [20, 10], [20, 20], [10, 20]])
    matrix = [[0.1, 0, 0], [0, 0.1, 0], [0, 0, 1]]
    transformed = transform_polygon_homography(polygon, matrix)
    assert_almost_equal(polygon_area(transformed), 1.0)


def run_all_tests():
    count = 0
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            value()
            count += 1
    return count


if __name__ == "__main__":
    print(f"TEST_GEOMETRY_R1_PASSED={run_all_tests()}")
