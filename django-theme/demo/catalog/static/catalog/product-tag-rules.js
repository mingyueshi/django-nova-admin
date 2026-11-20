document.querySelectorAll("#product-tag-ranking input[data-minimum-for]").forEach((minimum) => {
  const fields = minimum.form.elements;
  const tags = fields.namedItem(minimum.dataset.minimumFor);
  const mode = fields.namedItem(minimum.dataset.minimumFor + "_mode");
  const maximum = fields.namedItem(minimum.dataset.minimumFor + "_max");
  const counts = fields.namedItem(minimum.dataset.minimumFor + "_counts");
  const ranges = fields.namedItem(minimum.dataset.minimumFor + "_ranges");
  const mixedCountModes = ["values_or_ranges", "not_values_or_ranges"];
  const infinityName = /[iIｉＩ][nNｎＮ][fFｆＦ](?:[iIｉＩ][nNｎＮ][iIｉＩ][tTｔＴ][yYｙＹ])?/g;

  function validateRanges() {
    const tagCount = tags.selectedOptions.length;
    const mixed = mixedCountModes.includes(mode.value);
    const normalized = ranges.value.replace(/[０-９＜＞＝！]/g, char => char.normalize("NFKC"));
    const value = mixed ? normalized.replace(infinityName, "∞") : normalized;
    // Keep the comma inside an interval, including when the upper endpoint is unbounded.
    const separators = /、|[,，](?!\s*(?:(?:[0-9]+|\*|[+＋]?∞)\s*)?(?:\)|\]|）|］))/;
    const valid = ranges.disabled || !value || value.split(separators).every((part) => {
      const term = part.trim();
      if (mixed) {
        if (term === "*") return true;
        const interval = /^(\(|\[|（|［)\s*(?:(?:(0|[1-9][0-9]*)|\*|[-−－]∞)\s*)?[,，]\s*(?:(?:(0|[1-9][0-9]*)|\*|[+＋]?∞)\s*)?(\)|\]|）|］)$/.exec(term);
        if (interval) {
          const [, left, lower, upper, right] = interval;
          if (lower === undefined && !["(", "（"].includes(left)) return false;
          if (upper === undefined && ![")", "）"].includes(right)) return false;
          const low = Number(lower ?? 0);
          const high = Number(upper ?? tagCount);
          return low <= high && high <= tagCount;
        }
        const comparison = /^(?:(?:<>|><|[<>]=?|=[<>=]?|!=|[≠≤≥≦≧]|至多|至少|少于|多于)\s*(0|[1-9][0-9]*)(?:\s*个)?|(0|[1-9][0-9]*)\s*(?:个\s*)?(?:及以下|及以上))$/.exec(term);
        if (comparison) return Number(comparison[1] ?? comparison[2]) <= tagCount;
      }
      const pair = /^(0|[1-9][0-9]*)(?:\s*(?:-|到)\s*(0|[1-9][0-9]*))?$/.exec(term);
      if (!pair || (!mixed && pair[2] === undefined)) return false;
      const high = Number(pair[2] ?? pair[1]);
      return Number(pair[1]) <= high && high <= tagCount;
    });
    const error = mixed ? ranges.dataset.mixedError : ranges.dataset.rangeError;
    ranges.setCustomValidity(valid ? "" : error);
  }

  function update() {
    const range = mode.value === "range" || mode.value === "not_range";
    const usesMinimum = range || ["exact", "not_exact", "at_least"].includes(mode.value);
    const usesMaximum = range || mode.value === "at_most";
    const usesCounts = mode.value === "one_of" || mode.value === "not_one_of";
    const usesRanges = mixedCountModes.includes(mode.value) || ["any_range", "not_any_range"].includes(mode.value);
    tags.required = usesMinimum || usesMaximum || usesCounts || usesRanges;
    minimum.required = usesMinimum;
    minimum.disabled = !usesMinimum;
    minimum.closest("label").hidden = !usesMinimum;
    minimum.min = mode.value === "at_least" ? "1" : "0";
    minimum.max = String(tags.selectedOptions.length);
    maximum.required = usesMaximum;
    maximum.disabled = !usesMaximum;
    maximum.closest("label").hidden = !usesMaximum;
    maximum.max = String(tags.selectedOptions.length);
    maximum.min = range ? String(Math.max(0, minimum.valueAsNumber || 0)) : "0";
    counts.required = usesCounts;
    counts.disabled = !usesCounts;
    counts.closest("label").hidden = !usesCounts;
    const tagCount = tags.selectedOptions.length;
    let outOfRange = false;
    for (const option of counts.options) {
      const tooLarge = Number(option.value) > tagCount;
      option.disabled = tooLarge && !option.selected;
      if (option.selected && tooLarge) outOfRange = true;
    }
    counts.setCustomValidity(usesCounts && outOfRange ? counts.dataset.rangeError : "");
    ranges.required = usesRanges;
    ranges.disabled = !usesRanges;
    ranges.placeholder = mixedCountModes.includes(mode.value) ? "=０、２到４、＞＝６" : "0-1, 3-4";
    ranges.closest("label").hidden = !usesRanges;
    validateRanges();
  }

  mode.addEventListener("change", update);
  tags.addEventListener("change", update);
  counts.addEventListener("change", update);
  ranges.addEventListener("input", validateRanges);
  minimum.addEventListener("input", update);
  window.addEventListener("pageshow", update);
  update();
});
