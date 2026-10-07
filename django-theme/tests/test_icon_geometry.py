"""Geometric regressions, independent of SVG markup parsing or the generator."""
import math
import re
from xml.etree import ElementTree

from django.test import SimpleTestCase

from nova_admin.icons import ICON_PATHS
from tests.icon_geometry_fixtures import LEGACY_DJANGO, LEGACY_PREVIEW


def segments(path):
    """Resolve SVG relative/implicit commands to absolute drawing coordinates."""
    tokens = re.findall(r"[A-Za-z]|[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?", path)
    sizes = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7}
    result, current, origin, previous, control = [], (0, 0), (0, 0), None, None
    index, command = 0, None
    while index < len(tokens):
        if tokens[index].isalpha():
            command = tokens[index]
            index += 1
        kind = command.upper()
        if kind == "Z":
            result.append(("Z", current, origin))
            current, previous, control = origin, kind, None
            command = None
            continue
        values = [float(v) for v in tokens[index:index + sizes[kind]]]
        if len(values) != sizes[kind]:
            raise ValueError("Incomplete SVG command")
        index += sizes[kind]
        relative = command.islower()
        def point(x, y):
            return (x + current[0], y + current[1]) if relative else (x, y)
        if kind in {"M", "L", "T"}:
            end = point(*values)
            if kind == "M":
                result.append(("M", end))
                origin = end
                command = "l" if relative else "L"
            elif kind == "T":
                first = tuple(2 * a - b for a, b in zip(current, control)) if previous in {"Q", "T"} else current
                result.append(("Q", current, first, end))
                control = first
            else:
                result.append(("L", current, end))
        elif kind == "H":
            end = (values[0] + current[0] if relative else values[0], current[1])
            result.append(("L", current, end))
        elif kind == "V":
            end = (current[0], values[0] + current[1] if relative else values[0])
            result.append(("L", current, end))
        elif kind in {"C", "S", "Q"}:
            points = [point(*values[i:i + 2]) for i in range(0, len(values), 2)]
            if kind == "S":
                first = tuple(2 * a - b for a, b in zip(current, control)) if previous in {"C", "S"} else current
                points.insert(0, first)
            result.append(("Q" if kind == "Q" else "C", current, *points))
            end, control = points[-1], points[-2]
        elif kind == "A":
            end = point(*values[-2:])
            result.append(("A", current, tuple(values[:5]), end))
        else:
            raise ValueError(f"Unsupported SVG command: {kind}")
        if kind not in {"C", "S", "Q", "T"}:
            control = None
        current, previous = end, kind
    return result


def shape_paths(markup):
    """Interpret original separate primitives independently, resetting each origin."""
    result = []
    for node in ElementTree.fromstring(f"<svg>{markup}</svg>"):
        attrs = node.attrib
        if node.tag == "path":
            shape = segments(attrs["d"])
            if "transform" in attrs:
                # The only original transform is layers' fixed vertical offset.
                if attrs["transform"] != "translate(0 -2)":
                    raise ValueError("Unexpected legacy transform")
                shape = [tuple((item[0], item[1] - 2) if isinstance(item, tuple) and len(item) == 2 else item
                               for item in segment) for segment in shape]
            result.extend(shape)
        elif node.tag == "circle":
            x, y, r = (float(attrs[k]) for k in ("cx", "cy", "r"))
            result.extend(segments(f"M{x-r} {y}a{r} {r} 0 1 0 {2*r} 0a{r} {r} 0 1 0 {-2*r} 0"))
        elif node.tag == "rect":
            x, y, w, h = (float(attrs[k]) for k in ("x", "y", "width", "height"))
            r = float(attrs.get("rx", 0))
            result.extend(segments(f"M{x+r} {y}h{w-2*r}a{r} {r} 0 0 1 {r} {r}v{h-2*r}a{r} {r} 0 0 1 {-r} {r}h{-w+2*r}a{r} {r} 0 0 1 {-r} {-r}v{-h+2*r}a{r} {r} 0 0 1 {r} {-r}Z"))
        else:
            raise ValueError("Unexpected legacy primitive")
    return result


def bounds(drawing):
    """True centerline extrema for lines, Beziers and unrotated elliptic arcs."""
    points = []
    for segment in drawing:
        kind = segment[0]
        if kind in {"M", "L", "Z"}:
            points.extend(segment[1:])
        elif kind in {"C", "Q"}:
            controls = segment[1:]
            values = {0.0, 1.0}
            for axis in (0, 1):
                p = [point[axis] for point in controls]
                if kind == "Q":
                    a, b = p[0] - 2*p[1] + p[2], p[1] - p[0]
                    if a:
                        values.add(-b/a)
                else:
                    a, b, c = -p[0]+3*p[1]-3*p[2]+p[3], 2*(p[0]-2*p[1]+p[2]), p[1]-p[0]
                    if abs(a) < 1e-12:
                        if b:
                            values.add(-c/b)
                    elif b*b - 4*a*c >= 0:
                        root = math.sqrt(b*b - 4*a*c)
                        values.update(((-b+root)/(2*a), (-b-root)/(2*a)))
            for t in values:
                if 0 <= t <= 1:
                    coefficients = ((1-t)**3, 3*(1-t)**2*t, 3*(1-t)*t*t, t**3) if kind == "C" else ((1-t)**2, 2*(1-t)*t, t*t)
                    points.append(tuple(sum(c*p[axis] for c, p in zip(coefficients, controls)) for axis in (0, 1)))
        else:
            _, start, (rx, ry, rotation, large, sweep), end = segment
            if rotation != 0:
                raise ValueError("Catalog arc bounds require a separately reviewed rotation implementation")
            rx, ry = abs(rx), abs(ry)
            if not rx or not ry or start == end:
                points.extend((start, end))
                continue
            x, y = (start[0]-end[0])/2, (start[1]-end[1])/2
            scale = max(1.0, math.sqrt(x*x/(rx*rx) + y*y/(ry*ry)))
            rx, ry = rx*scale, ry*scale
            numerator = max(0.0, rx*rx*ry*ry - rx*rx*y*y - ry*ry*x*x)
            factor = math.sqrt(numerator/(rx*rx*y*y + ry*ry*x*x)) * (-1 if large == sweep else 1)
            cx, cy = factor*rx*y/ry, -factor*ry*x/rx
            theta = math.atan2((y-cy)/ry, (x-cx)/rx)
            finish = math.atan2((-y-cy)/ry, (-x-cx)/rx)
            delta = (finish-theta) % (2*math.pi) if sweep else -((theta-finish) % (2*math.pi))
            center = (cx+(start[0]+end[0])/2, cy+(start[1]+end[1])/2)
            points.extend((start, end))
            for angle in (0, math.pi/2, math.pi, 3*math.pi/2):
                distance = (angle-theta) % (2*math.pi) if sweep else (theta-angle) % (2*math.pi)
                if distance <= abs(delta) + 1e-9:
                    points.append((center[0]+rx*math.cos(angle), center[1]+ry*math.sin(angle)))
    return tuple(min(point[axis] for point in points) for axis in (0, 1)) + tuple(max(point[axis] for point in points) for axis in (0, 1))


def rounded(value):
    return tuple(rounded(item) for item in value) if isinstance(value, (tuple, list)) else round(value, 8) if isinstance(value, float) else value


class IconGeometryTests(SimpleTestCase):
    def test_every_preserved_preview_primitive_has_the_same_absolute_geometry(self):
        for name, markup in LEGACY_PREVIEW.items():
            if name in {"users", "settings"}:
                continue  # Shared names retain their original Django shape below.
            with self.subTest(name=name):
                self.assertEqual(rounded(segments(ICON_PATHS[name])), rounded(shape_paths(markup)))

    def test_original_django_shapes_keep_their_exact_geometry(self):
        for name, path in LEGACY_DJANGO.items():
            with self.subTest(name=name):
                self.assertEqual(rounded(segments(ICON_PATHS[name])), rounded(segments(path)))

    def test_merged_search_shield_and_mail_subpaths_have_independent_origins(self):
        expected = {"search": [(16, 16), (20.5, 20.5)], "shield": [(8, 12), (11, 15), (16, 9)], "mail": [(3, 6), (12, 13), (21, 6)]}
        for name, coordinates in expected.items():
            with self.subTest(name=name):
                drawing = segments(ICON_PATHS[name])
                start = max(i for i, item in enumerate(drawing) if item[0] == "M")
                self.assertEqual([item[-1] for item in drawing[start:]], coordinates)
                self.assertTrue(all(0 <= point[0] <= 24 and 0 <= point[1] <= 24 for point in coordinates))

    def test_previous_relative_origin_regressions_fail_geometry_and_bounds(self):
        regressions = {
            "search": ("M16 16l4.5 4.5", "m16 16 4.5 4.5"),
            "shield": ("M8 12l3 3 5-6", "m8 12 3 3 5-6"),
            "mail": ("M3 6l9 7 9-7", "m3 6 9 7 9-7"),
        }
        for name, (fixed, broken) in regressions.items():
            with self.subTest(name=name):
                self.assertIn(fixed, ICON_PATHS[name])
                shifted = segments(ICON_PATHS[name].replace(fixed, broken))
                self.assertNotEqual(rounded(shifted), rounded(shape_paths(LEGACY_PREVIEW[name])))
                self.assertGreater(max(bounds(shifted)[2:]), 24)

    def test_geometry_evaluator_uses_relative_origins_and_true_curve_extrema(self):
        drawing = segments("M10 10h2v2Z m2 3l1 1")
        self.assertEqual(drawing[-2:], [("M", (12, 13)), ("L", (12, 13), (13, 14))])
        self.assertEqual(bounds(segments("M0 0C0 8 8 8 8 0")), (0, 0, 8, 6))
        self.assertEqual(bounds(segments("M0 0Q4 8 8 0")), (0, 0, 8, 4))
        self.assertEqual(bounds(segments("M3 6a9 3 0 1 0 18 0a9 3 0 1 0-18 0")), (3, 3, 21, 9))

    def test_all_98_drawings_fit_their_viewbox_with_stroke_room(self):
        self.assertEqual(len(ICON_PATHS), 98)
        for name, path in ICON_PATHS.items():
            with self.subTest(name=name):
                x0, y0, x1, y1 = bounds(segments(path))
                # 1.65px stroke extends 0.825px either side of the centerline.
                self.assertGreaterEqual(x0, 0.825-1e-6)
                self.assertGreaterEqual(y0, 0.825-1e-6)
                self.assertLessEqual(x1, 23.175+1e-6)
                self.assertLessEqual(y1, 23.175+1e-6)
