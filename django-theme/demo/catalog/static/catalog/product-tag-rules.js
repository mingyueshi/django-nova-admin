document.querySelectorAll("#product-tag-ranking input[data-minimum-for]").forEach((minimum) => {
  const fields = minimum.form.elements;
  const tags = fields.namedItem(minimum.dataset.minimumFor);
  const mode = fields.namedItem(minimum.dataset.minimumFor + "_mode");
  const maximum = fields.namedItem(minimum.dataset.minimumFor + "_max");

  function update() {
    const range = mode.value === "range" || mode.value === "not_range";
    const usesMinimum = range || ["exact", "not_exact", "at_least"].includes(mode.value);
    const usesMaximum = range || mode.value === "at_most";
    tags.required = usesMinimum || usesMaximum;
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
  }

  mode.addEventListener("change", update);
  tags.addEventListener("change", update);
  minimum.addEventListener("input", update);
  window.addEventListener("pageshow", update);
  update();
});
