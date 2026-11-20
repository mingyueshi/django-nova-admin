"""Count distinct visible products for each tag on their product records."""
import re
from typing import NamedTuple

from django.db.models import Count, Exists, OuterRef, Q
from django.http import Http404
from django.utils.translation import pgettext

from .analysis_filters import ranking_key, ranking_selection
from .models import Product, Tag
from .navigation import visible_admin_objects


UNTAGGED = "untagged"
MIXED_COUNT_MODES = ("values_or_ranges", "not_values_or_ranges")
FULLWIDTH_COUNT_CHARS = str.maketrans("０１２３４５６７８９＜＞＝！", "0123456789<>=!")
# Each letter of "inf" or "infinity" accepts either width and case.
INFINITY_NAME = re.compile(r"[iIｉＩ][nNｎＮ][fFｆＦ](?:[iIｉＩ][nNｎＮ][iIｉＩ][tTｔＴ][yYｙＹ])?")
COUNT_COMPARISON = re.compile(
    r"(?:(<>|><|[<>]=?|=[<>=]?|!=|[≠≤≥≦≧]|至多|至少|少于|多于)\s*([0-9]+)(?:\s*个)?|([0-9]+)\s*(?:个\s*)?(及以下|及以上))"
)
# Capture only numeric endpoints. Infinity requires a minus on the left and allows a plus on the right.
BRACKETED_COUNT = re.compile(
    r"(\(|\[|（|［)\s*(?:(?:([0-9]+)|\*|[-−－]∞)\s*)?[,，]\s*"
    r"(?:(?:([0-9]+)|\*|[+＋]?∞)\s*)?(\)|\]|）|］)"
)
# Keep the comma before the upper endpoint and closing bracket inside the interval.
COUNT_SEPARATOR = re.compile(r"、|[,，](?!\s*(?:(?:[0-9]+|\*|[+＋]?∞)\s*)?(?:\)|\]|）|］))")


def readable_tags(request, owner, db):
    tags = Tag.objects.using(db)
    site = owner.admin_site
    if site.is_registered(Tag):
        tag_admin = site.get_model_admin(Tag)
        if tag_admin.has_module_permission(request) and tag_admin.has_view_or_change_permission(request):
            scope = tag_admin.get_queryset(request)
            if scope.db != db:
                return tags.none()
            allowed = visible_admin_objects(request, tag_admin, scope)
            tags = tags.filter(pk__in=allowed.order_by().values("pk"))
    # Product-only readers can see the tag names on readable product records.
    return tags


class CountBound(NamedTuple):
    # Merge and count using the included integer. Keep the operator for editable links, even for <0 and >max.
    included: int
    strict: bool = False


class TagRule(NamedTuple):
    keys: list[str]
    mode: str = ""
    minimum: int | None = None
    maximum: int | None = None
    counts: tuple[int, ...] = ()
    ranges: tuple[tuple[CountBound | None, CountBound | None], ...] = ()

    @property
    def ranges_text(self):
        terms = []
        for low, high in self.ranges:
            if high is None:
                if low and low.strict:
                    terms.append(f">{low.included - 1}")
                else:
                    terms.append(f">={low.included if low else 0}")
            elif low is None:
                terms.append(f"<{high.included + 1}" if high.strict else f"<={high.included}")
            elif low.strict or high.strict:
                left = f"({low.included - 1}" if low.strict else f"[{low.included}"
                right = f"{high.included + 1})" if high.strict else f"{high.included}]"
                terms.append(f"{left},{right}")
            elif self.mode in MIXED_COUNT_MODES and low == high:
                terms.append(str(low.included))
            else:
                terms.append(f"{low.included}-{high.included}")
        return ", ".join(terms)

    @property
    def match_counts(self):
        if self.ranges:
            return tuple(
                n for low, high in self.ranges
                for n in range(low.included if low else 0, (high.included if high else len(self.keys)) + 1)
            )
        return self.counts

    @property
    def match_maximum(self):
        return self.minimum if self.mode in ("exact", "not_exact") else self.maximum

    @property
    def negated(self):
        return self.mode in ("not_exact", "not_range", "not_one_of", "not_any_range", "not_values_or_ranges")

    @property
    def count_label(self):
        if self.ranges:
            if self.mode == "values_or_ranges":
                label = pgettext("Nova demo", "Match these counts or ranges (%(ranges)s)")
            elif self.mode == "not_values_or_ranges":
                label = pgettext("Nova demo", "Match none of these counts or ranges (%(ranges)s)")
            elif self.negated:
                label = pgettext("Nova demo", "Match none of these ranges (%(ranges)s)")
            else:
                label = pgettext("Nova demo", "Match any of these ranges (%(ranges)s)")
            return label % {"ranges": self.ranges_text}
        if self.counts:
            if self.negated:
                label = pgettext("Nova demo", "Match none of these counts (%(counts)s)")
            else:
                label = pgettext("Nova demo", "Match one of these counts (%(counts)s)")
            return label % {"counts": ", ".join(map(str, self.counts))}
        if self.mode == "at_most":
            return pgettext("Nova demo", "Match at most %(n)s") % {"n": self.maximum}
        if self.minimum is None:
            return ""
        if self.negated:
            if self.minimum == self.match_maximum:
                return pgettext("Nova demo", "Matched tag count differs from %(n)s") % {"n": self.minimum}
            return pgettext("Nova demo", "Matched tag count outside %(lower)s to %(upper)s") % {
                "lower": self.minimum, "upper": self.maximum,
            }
        if self.minimum == self.match_maximum:
            return pgettext("Nova demo", "Match exactly %(n)s") % {"n": self.minimum}
        if self.maximum is None:
            return pgettext("Nova demo", "Match at least %(n)s") % {"n": self.minimum}
        return pgettext("Nova demo", "Match %(lower)s to %(upper)s") % {"lower": self.minimum, "upper": self.maximum}

    def add_to_query(self, query, parameter):
        if self.keys:
            query.setlist(parameter, self.keys)
        if self.mode:
            query[parameter + "_mode"] = self.mode
        if self.minimum is not None:
            query[parameter + "_min"] = str(self.minimum)
        if self.maximum is not None:
            query[parameter + "_max"] = str(self.maximum)
        if self.counts:
            query.setlist(parameter + "_counts", [str(n) for n in self.counts])
        if self.ranges:
            query[parameter + "_ranges"] = self.ranges_text


def _count_bound(value, lowest, key_count):
    # Bound the input before integer conversion and count distinct selected options.
    if len(value) > len(str(key_count)) or not re.fullmatch(r"0|[1-9][0-9]*", value):
        raise Http404
    bound = int(value)
    if not lowest <= bound <= key_count:
        raise Http404
    return bound


def _term_intervals(term, key_count, mixed):
    if mixed and term == "*":
        return [(None, None)]
    if mixed and (interval := BRACKETED_COUNT.fullmatch(term)):
        left, lower, upper, right = interval.groups()
        open_left = left in ("(", "（")
        open_right = right in (")", "）")
        if lower is None and not open_left:
            raise Http404
        if upper is None and not open_right:
            raise Http404
        low = _count_bound(lower, 0, key_count) if lower is not None else None
        high = _count_bound(upper, low or 0, key_count) if upper is not None else None
        lower_bound = CountBound(low + open_left, open_left) if low is not None else None
        upper_bound = CountBound(high - open_right, open_right) if high is not None else None
        return [(lower_bound, upper_bound)]
    if mixed and (comparison := COUNT_COMPARISON.fullmatch(term)):
        operator = comparison[1] or comparison[4]
        threshold = _count_bound(comparison[2] or comparison[3], 0, key_count)
        if operator in ("<", "少于"):
            return [(None, CountBound(threshold - 1, strict=True))]
        if operator in (">", "多于"):
            return [(CountBound(threshold + 1, strict=True), None)]
        if operator in ("!=", "≠", "<>", "><"):
            return [(None, CountBound(threshold - 1, strict=True)), (CountBound(threshold + 1, strict=True), None)]
        bound = CountBound(threshold)
        if operator in ("=", "=="):
            return [(bound, bound)]
        return [(None, bound)] if operator in ("<=", "=<", "≤", "≦", "至多", "及以下") else [(bound, None)]
    pair = re.fullmatch(r"([0-9]+)(?:\s*(?:-|到)\s*([0-9]+))?", term)
    if not pair or (pair[2] is None and not mixed):
        raise Http404
    low = _count_bound(pair[1], 0, key_count)
    high = _count_bound(pair[2], low, key_count) if pair[2] is not None else low
    return [(CountBound(low), CountBound(high))]


def _count_ranges(value, key_count, *, mixed):
    value = value.translate(FULLWIDTH_COUNT_CHARS)
    if mixed:
        # Normalize before splitting so the comma in [3,INF) stays inside the interval.
        value = INFINITY_NAME.sub("∞", value)
    # Validate every term before merging, even when another term already covers all counts.
    intervals = []
    for part in COUNT_SEPARATOR.split(value):
        intervals.extend(_term_intervals(part.strip(), key_count, mixed))
    merged = []
    # On equal starting counts, prefer the original strict threshold (>2 over >=3).
    for low, high in sorted(intervals, key=lambda pair: (pair[0].included, not pair[0].strict) if pair[0] else (-1, False)):
        if low and high and low.included > high.included:
            continue
        if merged:
            start, end = merged[-1]
            if end is None:
                break
            if low is None or low.included <= end.included:
                merged[-1] = (start, None if high is None else max(end, high))
                continue
        merged.append((low, high))
    # Keep a valid expression on links and forms when every bounded interval contains zero integers.
    return tuple(merged) or (min(intervals),)


def _tag_rule(query, parameter, *, exporting):
    keys = list(dict.fromkeys(ranking_key(value, UNTAGGED) for value in query.getlist(parameter)))
    modes = query.getlist(parameter + "_mode")
    lower = query.getlist(parameter + "_min")
    upper = query.getlist(parameter + "_max")
    counts = query.getlist(parameter + "_counts")
    ranges = query.getlist(parameter + "_ranges")
    valid_modes = ("any", "all", "at_least", "at_most", "exact", "not_exact", "range", "not_range",
                   "one_of", "not_one_of", "any_range", "not_any_range", *MIXED_COUNT_MODES)
    if len(modes) > 1 or (modes and modes[0] not in valid_modes) or len(lower) > 1 or len(upper) > 1 or len(ranges) > 1:
        raise Http404
    mode = modes[0] if modes else ""
    is_range = mode in ("range", "not_range")
    uses_lower = is_range or mode in ("at_least", "exact", "not_exact")
    uses_upper = is_range or mode == "at_most"
    uses_counts = mode in ("one_of", "not_one_of")
    mixed = mode in MIXED_COUNT_MODES
    uses_ranges = mixed or mode in ("any_range", "not_any_range")
    # Plain HTML can send inactive bounds. Export URLs must only carry active ones.
    if exporting or not mode:
        if ((upper and not uses_upper) or (lower and not uses_lower) or
                (counts and not uses_counts) or (ranges and not uses_ranges)):
            raise Http404
    if uses_ranges:
        if not keys or not ranges:
            raise Http404
        intervals = _count_ranges(ranges[0], len(keys), mixed=mixed)
        return TagRule(keys, mode, ranges=intervals)
    if uses_counts:
        if not keys or not counts:
            raise Http404
        values = {_count_bound(value, 0, len(keys)) for value in counts}
        return TagRule(keys, mode, counts=tuple(sorted(values)))
    if uses_lower or uses_upper:
        if not keys:
            raise Http404
        minimum = None
        if uses_lower:
            minimum = _count_bound(query.get(parameter + "_min", ""), 1 if mode == "at_least" else 0, len(keys))
        maximum = _count_bound(query.get(parameter + "_max", ""), minimum or 0, len(keys)) if uses_upper else None
        return TagRule(keys, mode, minimum, maximum)

    if not keys:
        if exporting and mode and parameter == "chart_tag_exclude":
            raise Http404
        return TagRule([])
    if parameter == "chart_tag" and not mode:
        raise Http404
    return TagRule(keys, mode or "any")


def tag_selection(query, *, exporting):
    rule_params = ("chart_tag_mode", "chart_tag_min", "chart_tag_max", "chart_tag_counts", "chart_tag_ranges", "chart_tag_exclude",
                   "chart_tag_exclude_mode", "chart_tag_exclude_min", "chart_tag_exclude_max", "chart_tag_exclude_counts",
                   "chart_tag_exclude_ranges")
    if not any(name in query for name in rule_params):
        key = ranking_selection(query, "chart_tag", UNTAGGED)
        return TagRule([key] if key else []), TagRule([])
    if not query.get("chart_window"):
        raise Http404
    included = _tag_rule(query, "chart_tag", exporting=exporting)
    excluded = _tag_rule(query, "chart_tag_exclude", exporting=exporting)
    if exporting and not (included.keys or excluded.keys):
        raise Http404
    return included, excluded


def _positive_tag_match(memberships, keys, count_filter, *, matches_one):
    named = [key for key in keys if key != UNTAGGED]
    # Group on the through table so host joins cannot multiply or hide matches.
    matches = memberships.filter(tag_id__in=named).order_by().values("product_id")
    if count_filter is not None:
        matches = matches.alias(matched=Count("tag_id", distinct=True)).filter(count_filter)
    condition = Q(pk__in=matches)
    if matches_one and UNTAGGED in keys:
        condition |= ~Exists(memberships.filter(product_id=OuterRef("pk")))
    return condition


def _tag_match(memberships, rule):
    if rule.ranges:
        low, high = rule.ranges[0]
        if high is None and (low is None or low.included == 0):
            # (,) and its saved form >=0 cover every count. Selected keys are already authorized.
            no_products = Q(pk__in=[])
            return no_products if rule.negated else ~no_products
    maximum = rule.match_maximum
    counts = rule.match_counts
    if rule.ranges or counts:
        allowed = Q(matched__in=counts)
        if 0 in counts:
            # Rows with zero hits have no group. Remove only the disallowed positive counts.
            condition = ~_positive_tag_match(memberships, rule.keys, ~allowed, matches_one=1 not in counts)
        else:
            condition = _positive_tag_match(memberships, rule.keys, allowed, matches_one=1 in counts)
    elif rule.mode == "at_most" or rule.minimum == 0:
        # Products with no matching assignments have no group in the through table.
        # Within the visible queryset, 0..M is the complement of at least M+1.
        above = Q(matched__gt=maximum) if maximum else None
        condition = ~_positive_tag_match(memberships, rule.keys, above, matches_one=maximum == 0)
    else:
        minimum = len(rule.keys) if rule.mode == "all" else (rule.minimum or 1)
        count_filter = None
        if maximum is not None:
            count_filter = Q(matched__range=(minimum, maximum))
        elif minimum > 1:
            count_filter = Q(matched__gte=minimum)
        condition = _positive_tag_match(memberships, rule.keys, count_filter, matches_one=minimum == 1)
    return ~condition if rule.negated else condition


def select_tags(products, tags, included, excluded, period):
    requested = set(included.keys).union(excluded.keys)
    named = requested - {UNTAGGED}
    labels = {}
    if named:
        # Authorize both sides before evaluating even an empty or overlapping selection.
        visible = period.products_in(products, None).order_by().values("pk")
        names = tags.filter(pk__in=named, products__in=visible).order_by().values_list("pk", "name").distinct()
        labels = {str(pk): name for pk, name in names}
        if len(labels) != len(named):
            raise Http404
    if UNTAGGED in requested:
        labels[UNTAGGED] = pgettext("Nova demo", "Untagged (no assigned tags)") if included.mode or excluded.keys else pgettext("Nova demo", "Untagged")

    memberships = Product.tags.through.objects.using(products.db)
    selected = products.filter(_tag_match(memberships, included)) if included.keys else products
    if excluded.keys:
        selected = selected.exclude(_tag_match(memberships, excluded))
    return selected, labels


def tag_ranking(products, tags):
    # Start from the eligible product IDs so joins in the host queryset can
    # neither duplicate products nor suppress other tags on the same product.
    counts = tags.filter(products__in=products.order_by().values("pk")).values("pk", "name").annotate(
        total=Count("products", distinct=True)
    ).order_by("pk")
    rows = [{"key": str(row["pk"]), "label": row["name"], "total": row["total"]} for row in counts]
    untagged = products.filter(tags__isnull=True).order_by().values("pk").distinct().count()
    if untagged:
        rows.append({"key": UNTAGGED, "label": pgettext("Nova demo", "Untagged"), "total": untagged})
    return sorted(rows, key=lambda row: -row["total"])
