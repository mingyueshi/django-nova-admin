document.querySelectorAll("#product-tag-ranking input[data-minimum-for]").forEach((minimum) => {
  const fields = minimum.form.elements;
  const tags = fields.namedItem(minimum.dataset.minimumFor);
  const mode = fields.namedItem(minimum.dataset.minimumFor + "_mode");
  const maximum = fields.namedItem(minimum.dataset.minimumFor + "_max");
  const counts = fields.namedItem(minimum.dataset.minimumFor + "_counts");
  const ranges = fields.namedItem(minimum.dataset.minimumFor + "_ranges");

  function validateRanges() {
    const tagCount = tags.selectedOptions.length;
    const valid = ranges.disabled || !ranges.value || ranges.value.split(/[,，、]/).every((part) => {
      const pair = /^(0|[1-9][0-9]*)\s*(?:-|到)\s*(0|[1-9][0-9]*)$/.exec(part.trim());
      return pair && Number(pair[1]) <= Number(pair[2]) && Number(pair[2]) <= tagCount;
    });
    ranges.setCustomValidity(valid ? "" : ranges.dataset.rangeError);
  }

  function update() {
    const range = mode.value === "range" || mode.value === "not_range";
    const usesMinimum = range || ["exact", "not_exact", "at_least"].includes(mode.value);
    const usesMaximum = range || mode.value === "at_most";
    const usesCounts = mode.value === "one_of" || mode.value === "not_one_of";
    const usesRanges = mode.value === "any_range";
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
